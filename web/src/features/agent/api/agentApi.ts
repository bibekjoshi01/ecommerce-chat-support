import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

import { loadValidAgentAccessToken } from "../../../shared/lib/agentSession";
import type {
  AgentCloseConversationResponse,
  AgentConversationListResponse,
  AgentConversationMessagesResponse,
  AgentLoginResponse,
  AgentMessageExchangeResponse,
  AgentProfile,
  ConversationStatus,
} from "../../../shared/types/chat";

interface AgentLoginRequest {
  username: string;
  password: string;
}

interface AgentConversationsRequest {
  status?: ConversationStatus;
}

interface AgentConversationScopedRequest {
  conversationId: string;
}

interface AgentSendMessageRequest extends AgentConversationScopedRequest {
  content: string;
}

const resolveAgentBaseUrl = (): string => {
  const customerBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1/customer";
  return customerBaseUrl.replace(/\/customer\/?$/, "/agent");
};

export const agentApi = createApi({
  reducerPath: "agentApi",
  baseQuery: fetchBaseQuery({
    baseUrl: resolveAgentBaseUrl(),
    prepareHeaders: (headers) => {
      const accessToken = loadValidAgentAccessToken();
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
      return headers;
    },
  }),
  tagTypes: ["AgentProfile", "AgentConversations", "AgentConversationMessages"],
  endpoints: (builder) => ({
    loginAgent: builder.mutation<AgentLoginResponse, AgentLoginRequest>({
      query: (payload) => ({
        url: "/auth/login",
        method: "POST",
        body: payload,
      }),
      invalidatesTags: ["AgentProfile"],
    }),
    getAgentProfile: builder.query<AgentProfile, void>({
      query: () => "/me",
      providesTags: ["AgentProfile"],
    }),
    listConversations: builder.query<
      AgentConversationListResponse,
      AgentConversationsRequest
    >({
      query: ({ status }) => ({
        url: "/conversations",
        params: status ? { status } : undefined,
      }),
      providesTags: ["AgentConversations"],
    }),
    getConversationMessages: builder.query<
      AgentConversationMessagesResponse,
      AgentConversationScopedRequest
    >({
      query: ({ conversationId }) => `/conversations/${conversationId}/messages`,
      providesTags: (_result, _error, request) => [
        { type: "AgentConversationMessages", id: request.conversationId },
      ],
    }),
    sendAgentMessage: builder.mutation<
      AgentMessageExchangeResponse,
      AgentSendMessageRequest
    >({
      query: ({ conversationId, content }) => ({
        url: `/conversations/${conversationId}/messages`,
        method: "POST",
        body: { content },
      }),
      invalidatesTags: (_result, _error, request) => [
        "AgentConversations",
        { type: "AgentConversationMessages", id: request.conversationId },
      ],
    }),
    closeConversation: builder.mutation<
      AgentCloseConversationResponse,
      AgentConversationScopedRequest
    >({
      query: ({ conversationId }) => ({
        url: `/conversations/${conversationId}/close`,
        method: "POST",
      }),
      invalidatesTags: (_result, _error, request) => [
        "AgentConversations",
        { type: "AgentConversationMessages", id: request.conversationId },
      ],
    }),
  }),
});

export const {
  useCloseConversationMutation,
  useLoginAgentMutation,
  useLazyGetAgentProfileQuery,
  useLazyGetConversationMessagesQuery,
  useLazyListConversationsQuery,
  useSendAgentMessageMutation,
} = agentApi;
