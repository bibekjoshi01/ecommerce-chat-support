import { FetchBaseQueryError } from "@reduxjs/toolkit/query";
import { useEffect, useMemo, useState } from "react";

import { useAppDispatch, useAppSelector } from "../../../app/hooks";
import { loadOrCreateSessionId } from "../../../shared/lib/session";
import type { BotExchangeResponse, Message, MessageKind } from "../../../shared/types/chat";
import {
  useSendQuickReplyMutation,
  useSendTextMessageMutation,
  useStartConversationMutation,
} from "../api/chatApi";
import { appendExchange, hydrateFromBootstrap, setSessionId } from "./chatSlice";

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
}

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

  const [draft, setDraft] = useState("");
  const [uiError, setUiError] = useState<string | null>(null);
  const [isAssistantTyping, setIsAssistantTyping] = useState(false);
  const [pendingCustomerMessages, setPendingCustomerMessages] = useState<Message[]>(
    [],
  );

  const isSending = isSendingText || isSendingQuickReply;
  const isConversationClosed = conversation?.status === "closed";

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

  const removePendingMessage = (pendingMessageId: string) => {
    setPendingCustomerMessages((current) =>
      current.filter((message) => message.id !== pendingMessageId),
    );
  };

  const runSendFlow = async ({ content, kind, send }: SendFlowInput) => {
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

      setIsAssistantTyping(true);
      await wait(ASSISTANT_REPLY_DELAY_MS);

      dispatch(appendExchange(exchange));
    } catch (error) {
      removePendingMessage(pendingMessage.id);
      setUiError(toErrorMessage(error));
    } finally {
      setIsAssistantTyping(false);
    }
  };

  const sendDraft = async () => {
    if (!conversation || !sessionId) {
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
      send: () =>
        sendTextMessage({
          conversationId: conversation.id,
          sessionId,
          content,
        }).unwrap(),
    });
  };

  const sendQuickQuestion = async (faqSlug: string) => {
    if (!conversation || !sessionId) {
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
    isAssistantTyping,
    isConversationClosed,
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
