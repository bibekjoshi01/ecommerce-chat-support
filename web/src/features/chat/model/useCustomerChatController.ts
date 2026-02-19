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
  const [isAssistantTyping, setIsAssistantTyping] = useState(false);
  const [pendingCustomerMessages, setPendingCustomerMessages] = useState<Message[]>(
    [],
  );
  const [isRealtimeConnected, setIsRealtimeConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  const isSending = isSendingText || isSendingQuickReply || isEscalatingToAgent;
  const isConversationClosed = conversation?.status === "closed";
  const isAutomatedMode = conversation?.status === "automated";
  const isAgentMode = conversation?.status === "agent";

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
    const websocket = new WebSocket(
      buildRealtimeWsUrl({
        role: "customer",
        conversation_id: conversation.id,
        customer_session_id: sessionId,
      }),
    );

    socketRef.current = websocket;

    websocket.onopen = () => {
      if (closedByCleanup) {
        return;
      }
      setIsRealtimeConnected(true);
    };

    websocket.onclose = () => {
      if (!closedByCleanup) {
        setIsRealtimeConnected(false);
      }
    };

    websocket.onerror = () => {
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
      }
    };

    return () => {
      closedByCleanup = true;
      setIsRealtimeConnected(false);
      if (socketRef.current === websocket) {
        socketRef.current = null;
      }
      websocket.close();
    };
  }, [conversation?.id, dispatch, sessionId]);

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
      await wait(REQUEST_DELAY_MS);
      const exchange = await send();
      removePendingMessage(pendingMessage.id);

      if (simulateAssistantReply) {
        setIsAssistantTyping(true);
        await wait(ASSISTANT_REPLY_DELAY_MS);
      }

      dispatch(appendExchange(exchange));
    } catch (error) {
      removePendingMessage(pendingMessage.id);
      setUiError(toErrorMessage(error));
    } finally {
      setIsAssistantTyping(false);
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
    setIsAssistantTyping(false);

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
