import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

import type {
  AgentCloseConversationResponse,
  AgentConversationListResponse,
  AgentConversationMessagesResponse,
  AgentMessageExchangeResponse,
  AgentProfile,
  ConversationStatus,
} from "../../../shared/types/chat";

interface RegisterAgentRequest {
  display_name: string;
  max_active_chats: number;
  start_online: boolean;
}

interface AgentScopedRequest {
  agentId: string;
}

interface AgentConversationsRequest extends AgentScopedRequest {
  status?: ConversationStatus;
}

interface AgentConversationScopedRequest extends AgentScopedRequest {
  conversationId: string;
}

interface AgentSendMessageRequest extends AgentConversationScopedRequest {
  content: string;
}

interface SetPresenceRequest extends AgentScopedRequest {
  presence: "online" | "offline";
}

const resolveAgentBaseUrl = (): string => {
  const customerBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1/customer";
  return customerBaseUrl.replace(/\/customer\/?$/, "/agent");
};

export const agentApi = createApi({
  reducerPath: "agentApi",
  baseQuery: fetchBaseQuery({
    baseUrl: resolveAgentBaseUrl(),
  }),
  tagTypes: ["AgentProfile", "AgentConversations", "AgentConversationMessages"],
  endpoints: (builder) => ({
    registerAgent: builder.mutation<AgentProfile, RegisterAgentRequest>({
      query: (payload) => ({
        url: "/register",
        method: "POST",
        body: payload,
      }),
      invalidatesTags: ["AgentProfile", "AgentConversations"],
    }),
    getAgentProfile: builder.query<AgentProfile, AgentScopedRequest>({
      query: ({ agentId }) => ({
        url: "/me",
        headers: {
          "X-Agent-Id": agentId,
        },
      }),
      providesTags: ["AgentProfile"],
    }),
    setAgentPresence: builder.mutation<AgentProfile, SetPresenceRequest>({
      query: ({ agentId, presence }) => ({
        url: "/presence",
        method: "POST",
        body: { presence },
        headers: {
          "X-Agent-Id": agentId,
        },
      }),
      invalidatesTags: ["AgentProfile"],
    }),
    listConversations: builder.query<
      AgentConversationListResponse,
      AgentConversationsRequest
    >({
      query: ({ agentId, status }) => ({
        url: "/conversations",
        params: status ? { status } : undefined,
        headers: {
          "X-Agent-Id": agentId,
        },
      }),
      providesTags: ["AgentConversations"],
    }),
    getConversationMessages: builder.query<
      AgentConversationMessagesResponse,
      AgentConversationScopedRequest
    >({
      query: ({ agentId, conversationId }) => ({
        url: `/conversations/${conversationId}/messages`,
        headers: {
          "X-Agent-Id": agentId,
        },
      }),
      providesTags: (_result, _error, request) => [
        { type: "AgentConversationMessages", id: request.conversationId },
      ],
    }),
    sendAgentMessage: builder.mutation<
      AgentMessageExchangeResponse,
      AgentSendMessageRequest
    >({
      query: ({ agentId, conversationId, content }) => ({
        url: `/conversations/${conversationId}/messages`,
        method: "POST",
        body: { content },
        headers: {
          "X-Agent-Id": agentId,
        },
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
      query: ({ agentId, conversationId }) => ({
        url: `/conversations/${conversationId}/close`,
        method: "POST",
        headers: {
          "X-Agent-Id": agentId,
        },
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
  useLazyGetAgentProfileQuery,
  useLazyGetConversationMessagesQuery,
  useLazyListConversationsQuery,
  useRegisterAgentMutation,
  useSendAgentMessageMutation,
  useSetAgentPresenceMutation,
} = agentApi;
