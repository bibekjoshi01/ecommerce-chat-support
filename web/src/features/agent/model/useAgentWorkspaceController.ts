import { FetchBaseQueryError } from "@reduxjs/toolkit/query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "../../../app/hooks";
import {
  clearStoredAgentSession,
  loadStoredAgentSession,
} from "../../../shared/lib/agentSession";
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
  useSendAgentMessageMutation,
} from "../api/agentApi";
import {
  clearAgentIdentity,
  removeConversation,
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
import type { AgentConversationFilter } from "./agentSlice";

const WS_RETRY_BASE_DELAY_MS = 500;
const WS_RETRY_MAX_DELAY_MS = 5000;
const AGENT_TYPING_IDLE_MS = 1200;
const CONVERSATION_REFRESH_INTERVAL_MS = 15000;

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

const shouldShowConversationForFilter = (
  conversation: Conversation,
  statusFilter: AgentConversationFilter,
) => {
  if (conversation.status === "automated") {
    return false;
  }
  if (statusFilter === "all") {
    return true;
  }
  if (statusFilter === "closed") {
    return conversation.status === "closed";
  }
  if (statusFilter === "waiting") {
    return (
      conversation.status === "agent" && conversation.assigned_agent_id === null
    );
  }
  if (statusFilter === "active") {
    return (
      conversation.status === "agent" && conversation.assigned_agent_id !== null
    );
  }
  return false;
};

export const useAgentWorkspaceController = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const agentState = useAppSelector((state) => state.agent);

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
  const typingStateRef = useRef<{ conversationId: string | null; isTyping: boolean }>({
    conversationId: null,
    isTyping: false,
  });
  const typingStopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshRequestSeqRef = useRef(0);
  const statusFilterRef = useRef<AgentConversationFilter>("active");
  const conversationIdsRef = useRef<Set<string>>(new Set());

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
  statusFilterRef.current = statusFilter;
  conversationIdsRef.current = new Set(conversations.map((conversation) => conversation.id));

  const clearTypingTimer = useCallback(() => {
    if (typingStopTimerRef.current) {
      clearTimeout(typingStopTimerRef.current);
      typingStopTimerRef.current = null;
    }
  }, []);

  const sendTypingSignal = useCallback(
    (conversationId: string, isTyping: boolean) => {
      const current = typingStateRef.current;
      if (current.conversationId === conversationId && current.isTyping === isTyping) {
        return;
      }

      const websocket = socketRef.current;
      if (!websocket || websocket.readyState !== WebSocket.OPEN) {
        if (!isTyping) {
          typingStateRef.current = { conversationId: null, isTyping: false };
        }
        return;
      }

      try {
        websocket.send(
          JSON.stringify({
            action: "typing",
            conversation_id: conversationId,
            is_typing: isTyping,
          }),
        );
        typingStateRef.current = isTyping
          ? { conversationId, isTyping: true }
          : { conversationId: null, isTyping: false };
      } catch (_error) {
        if (!isTyping) {
          typingStateRef.current = { conversationId: null, isTyping: false };
        }
      }
    },
    [],
  );

  const signOut = useCallback(() => {
    clearStoredAgentSession();
    setDraft("");
    setUiError(null);
    setIsRealtimeConnected(false);
    clearTypingTimer();
    typingStateRef.current = { conversationId: null, isTyping: false };
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    dispatch(clearAgentIdentity());
    dispatch(resetAgentWorkspace());
    navigate("/agent/login", { replace: true });
  }, [clearTypingTimer, dispatch, navigate]);

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

  const bootstrapIdentity = useCallback(async () => {
    const storedSession = loadStoredAgentSession();
    if (!storedSession) {
      signOut();
      return;
    }

    try {
      const profileResponse = await fetchAgentProfile().unwrap();
      dispatch(
        setAgentIdentity({
          agentId: profileResponse.id,
          profile: profileResponse,
        }),
      );
      setUiError(null);
    } catch (error) {
      setUiError(toErrorMessage(error));
      signOut();
    }
  }, [dispatch, fetchAgentProfile, signOut]);

  useEffect(() => {
    if (!agentId) {
      void bootstrapIdentity();
    }
  }, [agentId, bootstrapIdentity]);

  const refreshConversations = useCallback(async () => {
    if (!agentId) {
      return;
    }

    const requestSeq = ++refreshRequestSeqRef.current;
    try {
      const response = await fetchConversations(
        {
          status:
            statusFilter === "closed"
              ? "closed"
              : statusFilter === "all"
                ? undefined
                : "agent",
        },
      ).unwrap();
      if (requestSeq !== refreshRequestSeqRef.current) {
        return;
      }
      dispatch(setConversations(response.items));
      setUiError(null);
    } catch (error) {
      if (requestSeq !== refreshRequestSeqRef.current) {
        return;
      }
      const message = toErrorMessage(error);
      setUiError(message);
      if (message.toLowerCase().includes("session")) {
        signOut();
      }
    }
  }, [agentId, dispatch, fetchConversations, signOut, statusFilter]);

  useEffect(() => {
    if (!agentId) {
      return;
    }
    void refreshConversations();
  }, [agentId, refreshConversations]);

  useEffect(() => {
    if (!agentId) {
      return;
    }
    const intervalId = setInterval(() => {
      void refreshConversations();
    }, CONVERSATION_REFRESH_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [agentId, refreshConversations]);

  useEffect(() => {
    if (!agentId || !selectedConversationId) {
      return;
    }
    let active = true;

    const loadMessages = async () => {
      try {
        const response = await fetchConversationMessages(
          {
            conversationId: selectedConversationId,
          },
        ).unwrap();
        if (!active) {
          return;
        }
        if (
          shouldShowConversationForFilter(
            response.conversation,
            statusFilterRef.current,
          )
        ) {
          dispatch(upsertConversation(response.conversation));
        } else {
          dispatch(removeConversation(response.conversation.id));
          return;
        }
        dispatch(
          setConversationMessages({
            conversationId: selectedConversationId,
            messages: response.messages,
          }),
        );
      } catch (error) {
        if (!active) {
          return;
        }
        const message = toErrorMessage(error);
        setUiError(message);
        if (message.toLowerCase().includes("session")) {
          signOut();
        }
      }
    };

    void loadMessages();
    return () => {
      active = false;
    };
  }, [agentId, dispatch, fetchConversationMessages, selectedConversationId, signOut]);

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

      const storedSession = loadStoredAgentSession();
      if (!storedSession) {
        signOut();
        return;
      }

      const websocket = new WebSocket(
        buildRealtimeWsUrl({
          role: "agent",
          access_token: storedSession.accessToken,
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

      websocket.onclose = (event) => {
        if (closedByCleanup) {
          return;
        }
        setIsRealtimeConnected(false);
        setLocalPresence("offline");
        clearTypingTimer();
        typingStateRef.current = { conversationId: null, isTyping: false };
        subscribedConversationIdRef.current = null;

        if (event.code === 1008) {
          setUiError("Session expired. Please login again.");
          signOut();
          return;
        }
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
          if (
            shouldShowConversationForFilter(conversation, statusFilterRef.current)
          ) {
            dispatch(upsertConversation(conversation));
          } else {
            dispatch(removeConversation(conversation.id));
          }
          return;
        }

        if (envelope.event === "chat.closed") {
          if (!isObject(envelope.payload)) {
            return;
          }
          const conversation = envelope.payload.conversation;
          if (isConversation(conversation)) {
            if (
              shouldShowConversationForFilter(conversation, statusFilterRef.current)
            ) {
              dispatch(upsertConversation(conversation));
            } else {
              dispatch(removeConversation(conversation.id));
            }
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
          const knownConversation =
            conversationIdsRef.current.has(message.conversation_id) ||
            selectedConversationIdRef.current === message.conversation_id;
          if (!knownConversation) {
            void refreshConversations();
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
      clearTypingTimer();
      typingStateRef.current = { conversationId: null, isTyping: false };
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      reconnectTimer = null;
      if (socketRef.current === activeSocket) {
        socketRef.current = null;
      }
      activeSocket?.close();
    };
  }, [agentId, clearTypingTimer, dispatch, refreshConversations, signOut]);

  useEffect(() => {
    const activeConversationId = selectedConversationId;
    const currentTypingState = typingStateRef.current;
    const trimmedDraft = draft.trim();
    const isConversationClosed = selectedConversation?.status === "closed";

    if (
      currentTypingState.conversationId &&
      currentTypingState.conversationId !== activeConversationId
    ) {
      sendTypingSignal(currentTypingState.conversationId, false);
    }

    clearTypingTimer();

    if (
      !activeConversationId ||
      !isRealtimeConnected ||
      isConversationClosed ||
      !trimmedDraft
    ) {
      if (activeConversationId) {
        sendTypingSignal(activeConversationId, false);
      } else {
        typingStateRef.current = { conversationId: null, isTyping: false };
      }
      return;
    }

    sendTypingSignal(activeConversationId, true);
    typingStopTimerRef.current = setTimeout(() => {
      sendTypingSignal(activeConversationId, false);
      typingStopTimerRef.current = null;
    }, AGENT_TYPING_IDLE_MS);
  }, [
    clearTypingTimer,
    draft,
    isRealtimeConnected,
    selectedConversation?.status,
    selectedConversationId,
    sendTypingSignal,
  ]);

  useEffect(() => {
    const websocket = socketRef.current;
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    const currentSubscription = subscribedConversationIdRef.current;
    if (currentSubscription && currentSubscription !== selectedConversationId) {
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

  const setFilter = (value: AgentConversationFilter) => {
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
    clearTypingTimer();
    sendTypingSignal(selectedConversationId, false);

    try {
      const response = await sendAgentMessage({
        conversationId: selectedConversationId,
        content,
      }).unwrap();
      dispatch(upsertConversation(response.conversation));
      dispatch(upsertConversationMessage(response.message));
      setDraft("");
    } catch (error) {
      const message = toErrorMessage(error);
      setUiError(message);
      if (message.toLowerCase().includes("session")) {
        signOut();
      }
    }
  };

  const closeSelectedConversation = async () => {
    if (!agentId || !selectedConversationId) {
      return;
    }

    setUiError(null);
    try {
      const response = await closeConversation({
        conversationId: selectedConversationId,
      }).unwrap();
      const shouldKeepVisible = shouldShowConversationForFilter(
        response.conversation,
        statusFilterRef.current,
      );

      if (shouldKeepVisible) {
        dispatch(upsertConversation(response.conversation));
      } else {
        dispatch(removeConversation(response.conversation.id));
      }
      if (response.system_message && shouldKeepVisible) {
        dispatch(upsertConversationMessage(response.system_message));
      }
    } catch (error) {
      const message = toErrorMessage(error);
      setUiError(message);
      if (message.toLowerCase().includes("session")) {
        signOut();
      }
    }
  };

  return {
    agentId,
    conversations,
    draft,
    isClosingConversation,
    isLoadingMessages,
    isRealtimeConnected,
    isRefreshingConversations,
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
    refreshConversations,
    selectConversationById,
    sendReply,
    signOut,
  };
};
