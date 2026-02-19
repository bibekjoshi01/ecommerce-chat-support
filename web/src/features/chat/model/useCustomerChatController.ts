import { FetchBaseQueryError } from "@reduxjs/toolkit/query";
import { useEffect, useMemo, useRef, useState } from "react";

import { useAppDispatch, useAppSelector } from "../../../app/hooks";
import { buildRealtimeWsUrl } from "../../../shared/lib/realtime";
import { loadOrCreateSessionId } from "../../../shared/lib/session";
import type {
  BotExchangeResponse,
  Conversation,
  Message,
  MessageKind,
  RealtimeEnvelope,
} from "../../../shared/types/chat";
import {
  useEscalateToAgentMutation,
  useSendQuickReplyMutation,
  useSendTextMessageMutation,
  useStartConversationMutation,
} from "../api/chatApi";
import {
  appendExchange,
  hydrateFromBootstrap,
  setSessionId,
  upsertConversation,
  upsertMessage,
} from "./chatSlice";

const REQUEST_DELAY_MS = 220;
const ASSISTANT_REPLY_DELAY_MS = 620;
const WS_RETRY_BASE_DELAY_MS = 500;
const WS_RETRY_MAX_DELAY_MS = 5000;
const AGENT_TYPING_RESET_MS = 1800;

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const sortByCreatedAt = (messages: Message[]) =>
  [...messages].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

const toErrorMessage = (error: unknown): string => {
  if (!error || typeof error !== "object") {
    return "Something went wrong. Please retry.";
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

  return "Request failed. Please try again.";
};

const createPendingMessage = ({
  conversationId,
  content,
  kind,
}: {
  conversationId: string;
  content: string;
  kind: MessageKind;
}): Message => ({
  id: `local_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
  conversation_id: conversationId,
  sender_type: "customer",
  kind,
  content,
  created_at: new Date().toISOString(),
});

interface SendFlowInput {
  content: string;
  kind: MessageKind;
  send: () => Promise<BotExchangeResponse>;
  simulateAssistantReply?: boolean;
}

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

export const useCustomerChatController = () => {
  const dispatch = useAppDispatch();

  const sessionId = useAppSelector((state) => state.chat.sessionId);
  const conversation = useAppSelector((state) => state.chat.conversation);
  const storedMessages = useAppSelector((state) => state.chat.messages);
  const quickQuestions = useAppSelector((state) => state.chat.quickQuestions);

  const [startConversation, { isLoading: isStartingConversation }] =
    useStartConversationMutation();
  const [sendTextMessage, { isLoading: isSendingText }] =
    useSendTextMessageMutation();
  const [sendQuickReply, { isLoading: isSendingQuickReply }] =
    useSendQuickReplyMutation();
  const [escalateToAgentMutation, { isLoading: isEscalatingToAgent }] =
    useEscalateToAgentMutation();

  const [draft, setDraft] = useState("");
  const [uiError, setUiError] = useState<string | null>(null);
  const [isBotTyping, setIsBotTyping] = useState(false);
  const [isAgentTyping, setIsAgentTyping] = useState(false);
  const [pendingCustomerMessages, setPendingCustomerMessages] = useState<Message[]>(
    [],
  );
  const [isRealtimeConnected, setIsRealtimeConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const agentTypingResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const conversationStatusRef = useRef<Conversation["status"] | null>(null);

  const isSending = isSendingText || isSendingQuickReply || isEscalatingToAgent;
  const isConversationClosed = conversation?.status === "closed";
  const isAutomatedMode = conversation?.status === "automated";
  const isAgentMode = conversation?.status === "agent";
  conversationStatusRef.current = conversation?.status ?? null;

  useEffect(() => {
    if (!sessionId) {
      dispatch(setSessionId(loadOrCreateSessionId()));
    }
  }, [dispatch, sessionId]);

  useEffect(() => {
    if (!sessionId || conversation) {
      return;
    }

    let mounted = true;

    const bootstrap = async () => {
      try {
        const response = await startConversation({
          customer_session_id: sessionId,
          force_new: false,
        }).unwrap();
        if (!mounted) {
          return;
        }
        dispatch(hydrateFromBootstrap(response));
      } catch (error) {
        if (mounted) {
          setUiError(toErrorMessage(error));
        }
      }
    };

    void bootstrap();
    return () => {
      mounted = false;
    };
  }, [conversation, dispatch, sessionId, startConversation]);

  useEffect(() => {
    if (!sessionId || !conversation?.id) {
      return;
    }

    let closedByCleanup = false;
    let reconnectAttempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let activeSocket: WebSocket | null = null;

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
          role: "customer",
          conversation_id: conversation.id,
          customer_session_id: sessionId,
        }),
      );

      activeSocket = websocket;
      socketRef.current = websocket;

      websocket.onopen = () => {
        if (closedByCleanup) {
          return;
        }
        reconnectAttempt = 0;
        setIsRealtimeConnected(true);
      };

      websocket.onclose = () => {
        if (closedByCleanup) {
          return;
        }
        setIsRealtimeConnected(false);
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

        if (envelope.event === "conversation.updated") {
          if (!isObject(envelope.payload)) {
            return;
          }
          const nextConversation = envelope.payload.conversation;
          if (!isConversation(nextConversation)) {
            return;
          }
          dispatch(upsertConversation(nextConversation));
          if (nextConversation.status !== "agent") {
            if (agentTypingResetTimerRef.current) {
              clearTimeout(agentTypingResetTimerRef.current);
              agentTypingResetTimerRef.current = null;
            }
            setIsAgentTyping(false);
          }
          return;
        }

        if (envelope.event === "agent.typing") {
          if (!isObject(envelope.payload)) {
            return;
          }
          const payloadConversationId = envelope.payload.conversation_id;
          const isTyping = envelope.payload.is_typing;
          if (
            typeof payloadConversationId !== "string" ||
            payloadConversationId !== conversation.id ||
            typeof isTyping !== "boolean"
          ) {
            return;
          }
          if (conversationStatusRef.current !== "agent") {
            return;
          }

          if (agentTypingResetTimerRef.current) {
            clearTimeout(agentTypingResetTimerRef.current);
            agentTypingResetTimerRef.current = null;
          }

          setIsAgentTyping(isTyping);
          if (isTyping) {
            agentTypingResetTimerRef.current = setTimeout(() => {
              setIsAgentTyping(false);
              agentTypingResetTimerRef.current = null;
            }, AGENT_TYPING_RESET_MS);
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
          dispatch(upsertMessage(message));
          if (message.sender_type === "bot" || message.sender_type === "system") {
            setIsBotTyping(false);
          }
          if (message.sender_type === "agent") {
            if (agentTypingResetTimerRef.current) {
              clearTimeout(agentTypingResetTimerRef.current);
              agentTypingResetTimerRef.current = null;
            }
            setIsAgentTyping(false);
          }
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
      if (agentTypingResetTimerRef.current) {
        clearTimeout(agentTypingResetTimerRef.current);
        agentTypingResetTimerRef.current = null;
      }
      setIsAgentTyping(false);
    };
  }, [conversation?.id, dispatch, sessionId]);

  useEffect(() => {
    if (isAgentMode) {
      return;
    }
    if (agentTypingResetTimerRef.current) {
      clearTimeout(agentTypingResetTimerRef.current);
      agentTypingResetTimerRef.current = null;
    }
    setIsAgentTyping(false);
  }, [isAgentMode]);

  const removePendingMessage = (pendingMessageId: string) => {
    setPendingCustomerMessages((current) =>
      current.filter((message) => message.id !== pendingMessageId),
    );
  };

  const runSendFlow = async ({
    content,
    kind,
    send,
    simulateAssistantReply = true,
  }: SendFlowInput) => {
    if (!conversation || !sessionId || isConversationClosed) {
      return;
    }

    setUiError(null);

    const pendingMessage = createPendingMessage({
      conversationId: conversation.id,
      content,
      kind,
    });
    setPendingCustomerMessages((current) => [...current, pendingMessage]);

    try {
      if (simulateAssistantReply) {
        setIsBotTyping(true);
      }
      await wait(REQUEST_DELAY_MS);
      const exchange = await send();
      removePendingMessage(pendingMessage.id);

      if (simulateAssistantReply && exchange.bot_message) {
        await wait(ASSISTANT_REPLY_DELAY_MS);
      }

      dispatch(appendExchange(exchange));
    } catch (error) {
      removePendingMessage(pendingMessage.id);
      setUiError(toErrorMessage(error));
    } finally {
      setIsBotTyping(false);
    }
  };

  const sendDraft = async () => {
    if (!conversation || !sessionId || !isAgentMode) {
      return;
    }

    const content = draft.trim();
    if (!content) {
      return;
    }

    setDraft("");
    await runSendFlow({
      content,
      kind: "text",
      simulateAssistantReply: false,
      send: () =>
        sendTextMessage({
          conversationId: conversation.id,
          sessionId,
          content,
        }).unwrap(),
    });
  };

  const sendQuickQuestion = async (faqSlug: string) => {
    if (!conversation || !sessionId || !isAutomatedMode) {
      return;
    }

    const matchedQuestion =
      quickQuestions.find((entry) => entry.slug === faqSlug)?.question ??
      "Quick question";

    await runSendFlow({
      content: matchedQuestion,
      kind: "quick_reply",
      send: () =>
        sendQuickReply({
          conversationId: conversation.id,
          sessionId,
          faqSlug,
        }).unwrap(),
    });
  };

  const escalateToAgent = async () => {
    if (!conversation || !sessionId || !isAutomatedMode) {
      return;
    }

    await runSendFlow({
      content: "Talk to an agent",
      kind: "quick_reply",
      send: () =>
        escalateToAgentMutation({
          conversationId: conversation.id,
          sessionId,
        }).unwrap(),
    });
  };

  const startNewConversation = async () => {
    if (!sessionId) {
      return;
    }

    setUiError(null);
    setPendingCustomerMessages([]);
    setIsBotTyping(false);
    setIsAgentTyping(false);
    if (agentTypingResetTimerRef.current) {
      clearTimeout(agentTypingResetTimerRef.current);
      agentTypingResetTimerRef.current = null;
    }

    try {
      const response = await startConversation({
        customer_session_id: sessionId,
        force_new: true,
      }).unwrap();
      dispatch(hydrateFromBootstrap(response));
      setDraft("");
    } catch (error) {
      setUiError(toErrorMessage(error));
    }
  };

  const messages = useMemo(
    () => sortByCreatedAt([...storedMessages, ...pendingCustomerMessages]),
    [pendingCustomerMessages, storedMessages],
  );
  const isAssistantTyping = isAgentMode ? isAgentTyping : isBotTyping;

  return {
    conversation,
    draft,
    escalateToAgent,
    isAgentMode,
    isAssistantTyping,
    isAutomatedMode,
    isConversationClosed,
    isEscalatingToAgent,
    isRealtimeConnected,
    isSending,
    isStartingConversation,
    messages,
    quickQuestions,
    sessionId,
    setDraft,
    sendDraft,
    sendQuickQuestion,
    startNewConversation,
    uiError,
  };
};
