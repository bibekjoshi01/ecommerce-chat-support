import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

import type {
  BotExchangeResponse,
  ConversationBootstrapResponse,
  ConversationMessagesResponse,
  QuickQuestion,
} from "../../../shared/types/chat";

interface StartConversationRequest {
  customer_session_id: string;
  force_new?: boolean;
}

interface ConversationScopedRequest {
  conversationId: string;
  sessionId: string;
}

interface SendTextMessageRequest extends ConversationScopedRequest {
  content: string;
}

interface SendQuickReplyRequest extends ConversationScopedRequest {
  faqSlug: string;
}

export const chatApi = createApi({
  reducerPath: "chatApi",
  baseQuery: fetchBaseQuery({
    baseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api/v1/customer",
  }),
  tagTypes: ["Conversation", "Messages", "QuickQuestions"],
  endpoints: (builder) => ({
    listQuickQuestions: builder.query<QuickQuestion[], void>({
      query: () => "/quick-questions",
      providesTags: ["QuickQuestions"],
    }),
    startConversation: builder.mutation<
      ConversationBootstrapResponse,
      StartConversationRequest
    >({
      query: (payload) => ({
        url: "/conversations/start",
        method: "POST",
        body: payload,
      }),
      invalidatesTags: ["Conversation", "Messages", "QuickQuestions"],
    }),
    getConversationMessages: builder.query<
      ConversationMessagesResponse,
      ConversationScopedRequest
    >({
      query: ({ conversationId, sessionId }) => ({
        url: `/conversations/${conversationId}/messages`,
        headers: {
          "X-Customer-Session-Id": sessionId,
        },
      }),
      providesTags: ["Conversation", "Messages"],
    }),
    sendTextMessage: builder.mutation<BotExchangeResponse, SendTextMessageRequest>({
      query: ({ conversationId, sessionId, content }) => ({
        url: `/conversations/${conversationId}/messages`,
        method: "POST",
        body: { content },
        headers: {
          "X-Customer-Session-Id": sessionId,
        },
      }),
      invalidatesTags: ["Conversation", "Messages", "QuickQuestions"],
    }),
    sendQuickReply: builder.mutation<BotExchangeResponse, SendQuickReplyRequest>({
      query: ({ conversationId, sessionId, faqSlug }) => ({
        url: `/conversations/${conversationId}/quick-replies/${faqSlug}`,
        method: "POST",
        headers: {
          "X-Customer-Session-Id": sessionId,
        },
      }),
      invalidatesTags: ["Conversation", "Messages", "QuickQuestions"],
    }),
    escalateToAgent: builder.mutation<BotExchangeResponse, ConversationScopedRequest>({
      query: ({ conversationId, sessionId }) => ({
        url: `/conversations/${conversationId}/escalate`,
        method: "POST",
        headers: {
          "X-Customer-Session-Id": sessionId,
        },
      }),
      invalidatesTags: ["Conversation", "Messages", "QuickQuestions"],
    }),
  }),
});

export const {
  useLazyGetConversationMessagesQuery,
  useEscalateToAgentMutation,
  useSendQuickReplyMutation,
  useSendTextMessageMutation,
  useStartConversationMutation,
} = chatApi;
