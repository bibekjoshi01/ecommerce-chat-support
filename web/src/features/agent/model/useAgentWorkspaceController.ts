import { FetchBaseQueryError } from "@reduxjs/toolkit/query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAppDispatch, useAppSelector } from "../../../app/hooks";
import {
  clearStoredAgentIdentity,
  createDefaultAgentDisplayName,
  loadStoredAgentIdentity,
  saveStoredAgentIdentity,
} from "../../../shared/lib/agentIdentity";
import { buildRealtimeWsUrl } from "../../../shared/lib/realtime";
import type {
  AgentProfile,
  Conversation,
  Message,
  RealtimeEnvelope,
} from "../../../shared/types/chat";
import {
  useCloseConversationMutation,
  useLazyGetAgentProfileQuery,
  useLazyGetConversationMessagesQuery,
  useLazyListConversationsQuery,
  useRegisterAgentMutation,
  useSendAgentMessageMutation,
} from "../api/agentApi";
import {
  clearAgentIdentity,
  resetAgentWorkspace,
  selectConversation,
  setAgentIdentity,
  setAgentProfile,
  setConversationMessages,
  setConversations,
  setStatusFilter,
  upsertConversation,
  upsertConversationMessage,
} from "./agentSlice";

const WS_RETRY_BASE_DELAY_MS = 500;
const WS_RETRY_MAX_DELAY_MS = 5000;

const toErrorMessage = (error: unknown): string => {
  if (!error || typeof error !== "object") {
    return "Request failed. Please try again.";
  }

  if ("status" in error) {
    const apiError = error as FetchBaseQueryError;
    if (
      apiError.data &&
      typeof apiError.data === "object" &&
      "detail" in apiError.data
    ) {
      const detail = (apiError.data as { detail?: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
    }
    if (typeof apiError.data === "string") {
      return apiError.data;
    }
  }

  if ("message" in error && typeof error.message === "string") {
    return error.message;
  }

  return "Something went wrong. Please retry.";
};

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const isConversation = (value: unknown): value is Conversation => {
  if (!isObject(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.customer_session_id === "string" &&
    typeof value.status === "string" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
};

const isMessage = (value: unknown): value is Message => {
  if (!isObject(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.conversation_id === "string" &&
    typeof value.sender_type === "string" &&
    typeof value.kind === "string" &&
    typeof value.content === "string" &&
    typeof value.created_at === "string"
  );
};

export const useAgentWorkspaceController = () => {
  const dispatch = useAppDispatch();
  const agentState = useAppSelector((state) => state.agent);

  const [registerAgent, { isLoading: isRegisteringAgent }] =
    useRegisterAgentMutation();
  const [fetchAgentProfile] = useLazyGetAgentProfileQuery();
  const [fetchConversations, { isFetching: isRefreshingConversations }] =
    useLazyListConversationsQuery();
  const [fetchConversationMessages, { isFetching: isLoadingMessages }] =
    useLazyGetConversationMessagesQuery();
  const [sendAgentMessage, { isLoading: isSendingMessage }] =
    useSendAgentMessageMutation();
  const [closeConversation, { isLoading: isClosingConversation }] =
    useCloseConversationMutation();

  const [draft, setDraft] = useState("");
  const [uiError, setUiError] = useState<string | null>(null);
  const [isRealtimeConnected, setIsRealtimeConnected] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const subscribedConversationIdRef = useRef<string | null>(null);
  const selectedConversationIdRef = useRef<string | null>(null);
  const profileRef = useRef<AgentProfile | null>(null);

  const {
    agentId,
    profile,
    statusFilter,
    conversations,
    selectedConversationId,
    messagesByConversation,
    unreadByConversation,
  } = agentState;

  selectedConversationIdRef.current = selectedConversationId;
  profileRef.current = profile;

  const selectedConversation = useMemo(
    () =>
      selectedConversationId
        ? conversations.find((conversation) => conversation.id === selectedConversationId) ??
          null
        : null,
    [conversations, selectedConversationId],
  );

  const selectedConversationMessages = useMemo(() => {
    if (!selectedConversationId) {
      return [];
    }
    return messagesByConversation[selectedConversationId] ?? [];
  }, [messagesByConversation, selectedConversationId]);

  const ensureIdentity = useCallback(async (): Promise<AgentProfile | null> => {
    const storedIdentity = loadStoredAgentIdentity();
    if (storedIdentity) {
      try {
        const profileResponse = await fetchAgentProfile(
          { agentId: storedIdentity.agentId },
          true,
        ).unwrap();
        const persistedIdentity = saveStoredAgentIdentity({
          agentId: profileResponse.id,
          displayName: profileResponse.display_name,
        });
        dispatch(
          setAgentIdentity({
            agentId: persistedIdentity.agentId,
            profile: profileResponse,
          }),
        );
        return profileResponse;
      } catch (_error) {
        clearStoredAgentIdentity();
      }
    }

    const fallbackName = storedIdentity?.displayName ?? createDefaultAgentDisplayName();
    const registered = await registerAgent({
      display_name: fallbackName,
      max_active_chats: 5,
      start_online: false,
    }).unwrap();
    const persistedIdentity = saveStoredAgentIdentity({
      agentId: registered.id,
      displayName: registered.display_name,
    });
    dispatch(
      setAgentIdentity({
        agentId: persistedIdentity.agentId,
        profile: registered,
      }),
    );
    return registered;
  }, [dispatch, fetchAgentProfile, registerAgent]);

  useEffect(() => {
    let active = true;

    const bootstrap = async () => {
      try {
        setUiError(null);
        await ensureIdentity();
      } catch (error) {
        if (active) {
          setUiError(toErrorMessage(error));
        }
      }
    };

    if (!agentId) {
      void bootstrap();
    }

    return () => {
      active = false;
    };
  }, [agentId, ensureIdentity]);

  const refreshConversations = useCallback(async () => {
    if (!agentId) {
      return;
    }

    try {
      const response = await fetchConversations(
        {
          agentId,
          status: statusFilter === "all" ? undefined : statusFilter,
        },
        true,
      ).unwrap();
      dispatch(setConversations(response.items));
    } catch (error) {
      setUiError(toErrorMessage(error));
    }
  }, [agentId, dispatch, fetchConversations, statusFilter]);

  useEffect(() => {
    if (!agentId) {
      return;
    }
    void refreshConversations();
  }, [agentId, refreshConversations, statusFilter]);

  useEffect(() => {
    if (!agentId || !selectedConversationId) {
      return;
    }
    let active = true;

    const loadMessages = async () => {
      try {
        const response = await fetchConversationMessages(
          {
            agentId,
            conversationId: selectedConversationId,
          },
          true,
        ).unwrap();
        if (!active) {
          return;
        }
        dispatch(upsertConversation(response.conversation));
        dispatch(
          setConversationMessages({
            conversationId: selectedConversationId,
            messages: response.messages,
          }),
        );
      } catch (error) {
        if (active) {
          setUiError(toErrorMessage(error));
        }
      }
    };

    void loadMessages();
    return () => {
      active = false;
    };
  }, [agentId, dispatch, fetchConversationMessages, selectedConversationId]);

  useEffect(() => {
    if (!agentId) {
      return;
    }

    let closedByCleanup = false;
    let reconnectAttempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let activeSocket: WebSocket | null = null;

    const setLocalPresence = (presence: AgentProfile["presence"]) => {
      const currentProfile = profileRef.current;
      if (!currentProfile || currentProfile.presence === presence) {
        return;
      }
      dispatch(
        setAgentProfile({
          ...currentProfile,
          presence,
        }),
      );
    };

    const scheduleReconnect = () => {
      if (closedByCleanup || reconnectTimer) {
        return;
      }

      const delay = Math.min(
        WS_RETRY_MAX_DELAY_MS,
        WS_RETRY_BASE_DELAY_MS * 2 ** reconnectAttempt,
      );
      reconnectAttempt += 1;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, delay);
    };

    const connect = () => {
      if (closedByCleanup) {
        return;
      }

      const websocket = new WebSocket(
        buildRealtimeWsUrl({
          role: "agent",
          agent_id: agentId,
        }),
      );

      activeSocket = websocket;
      socketRef.current = websocket;
      subscribedConversationIdRef.current = null;

      websocket.onopen = () => {
        if (closedByCleanup) {
          return;
        }
        reconnectAttempt = 0;
        setIsRealtimeConnected(true);
        setUiError(null);
        setLocalPresence("online");
        if (selectedConversationIdRef.current) {
          websocket.send(
            JSON.stringify({
              action: "subscribe_conversation",
              conversation_id: selectedConversationIdRef.current,
            }),
          );
          subscribedConversationIdRef.current = selectedConversationIdRef.current;
        }
      };

      websocket.onclose = () => {
        if (closedByCleanup) {
          return;
        }
        setIsRealtimeConnected(false);
        setLocalPresence("offline");
        subscribedConversationIdRef.current = null;
        scheduleReconnect();
      };

      websocket.onerror = () => {
        if (closedByCleanup) {
          return;
        }
        setIsRealtimeConnected(false);
      };

      websocket.onmessage = (event) => {
        let envelope: RealtimeEnvelope<unknown> | null = null;
        try {
          envelope = JSON.parse(event.data) as RealtimeEnvelope<unknown>;
        } catch (_error) {
          return;
        }
        if (!envelope || typeof envelope.event !== "string") {
          return;
        }

        if (
          envelope.event === "conversation.updated" ||
          envelope.event === "agent.assigned"
        ) {
          if (!isObject(envelope.payload)) {
            return;
          }
          const conversation = envelope.payload.conversation;
          if (!isConversation(conversation)) {
            return;
          }
          dispatch(upsertConversation(conversation));
          return;
        }

        if (envelope.event === "chat.closed") {
          if (!isObject(envelope.payload)) {
            return;
          }
          const conversation = envelope.payload.conversation;
          if (isConversation(conversation)) {
            dispatch(upsertConversation(conversation));
          }
          return;
        }

        if (envelope.event === "message.created") {
          if (!isObject(envelope.payload)) {
            return;
          }
          const message = envelope.payload.message;
          if (!isMessage(message)) {
            return;
          }
          dispatch(upsertConversationMessage(message));
        }
      };
    };

    connect();

    return () => {
      closedByCleanup = true;
      setIsRealtimeConnected(false);
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      reconnectTimer = null;
      if (socketRef.current === activeSocket) {
        socketRef.current = null;
      }
      activeSocket?.close();
    };
  }, [agentId, dispatch]);

  useEffect(() => {
    const websocket = socketRef.current;
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    const currentSubscription = subscribedConversationIdRef.current;
    if (
      currentSubscription &&
      currentSubscription !== selectedConversationId
    ) {
      websocket.send(
        JSON.stringify({
          action: "unsubscribe_conversation",
          conversation_id: currentSubscription,
        }),
      );
      subscribedConversationIdRef.current = null;
    }

    if (
      selectedConversationId &&
      selectedConversationId !== subscribedConversationIdRef.current
    ) {
      websocket.send(
        JSON.stringify({
          action: "subscribe_conversation",
          conversation_id: selectedConversationId,
        }),
      );
      subscribedConversationIdRef.current = selectedConversationId;
    }
  }, [selectedConversationId, isRealtimeConnected]);

  const setFilter = (value: "all" | "automated" | "agent" | "closed") => {
    dispatch(setStatusFilter(value));
  };

  const selectConversationById = (conversationId: string) => {
    dispatch(selectConversation(conversationId));
    setDraft("");
  };

  const sendReply = async () => {
    if (!agentId || !selectedConversationId) {
      return;
    }
    const content = draft.trim();
    if (!content) {
      return;
    }
    setUiError(null);

    try {
      const response = await sendAgentMessage({
        agentId,
        conversationId: selectedConversationId,
        content,
      }).unwrap();
      dispatch(upsertConversation(response.conversation));
      dispatch(upsertConversationMessage(response.message));
      setDraft("");
    } catch (error) {
      setUiError(toErrorMessage(error));
    }
  };

  const closeSelectedConversation = async () => {
    if (!agentId || !selectedConversationId) {
      return;
    }

    setUiError(null);
    try {
      const response = await closeConversation({
        agentId,
        conversationId: selectedConversationId,
      }).unwrap();
      dispatch(upsertConversation(response.conversation));
      if (response.system_message) {
        dispatch(upsertConversationMessage(response.system_message));
      }
    } catch (error) {
      setUiError(toErrorMessage(error));
    }
  };

  const reconnectAgent = () => {
    setUiError(null);
    clearStoredAgentIdentity();
    dispatch(clearAgentIdentity());
    dispatch(resetAgentWorkspace());
    setDraft("");
  };

  return {
    agentId,
    conversations,
    draft,
    isClosingConversation,
    isLoadingMessages,
    isRealtimeConnected,
    isRefreshingConversations,
    isRegisteringAgent,
    isSendingMessage,
    profile,
    selectedConversation,
    selectedConversationId,
    selectedConversationMessages,
    setDraft,
    setFilter,
    statusFilter,
    uiError,
    unreadByConversation,
    closeSelectedConversation,
    reconnectAgent,
    refreshConversations,
    selectConversationById,
    sendReply,
  };
};
