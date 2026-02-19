import { PayloadAction, createSlice } from "@reduxjs/toolkit";

import type { AgentProfile, Conversation, ConversationStatus, Message } from "../../../shared/types/chat";

export type AgentConversationFilter = ConversationStatus | "all";

interface AgentState {
  agentId: string | null;
  profile: AgentProfile | null;
  statusFilter: AgentConversationFilter;
  conversations: Conversation[];
  selectedConversationId: string | null;
  messagesByConversation: Record<string, Message[]>;
  unreadByConversation: Record<string, number>;
}

const initialState: AgentState = {
  agentId: null,
  profile: null,
  statusFilter: "agent",
  conversations: [],
  selectedConversationId: null,
  messagesByConversation: {},
  unreadByConversation: {},
};

const sortConversations = (items: Conversation[]) =>
  [...items].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

const sortMessages = (messages: Message[]) =>
  [...messages].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

const mergeMessages = (existing: Message[], incoming: Message[]) => {
  const byId = new Map(existing.map((message) => [message.id, message]));
  for (const message of incoming) {
    byId.set(message.id, message);
  }
  return sortMessages([...byId.values()]);
};

const mergeConversations = (
  existing: Conversation[],
  incoming: Conversation[],
): Conversation[] => {
  const byId = new Map(existing.map((conversation) => [conversation.id, conversation]));
  for (const conversation of incoming) {
    byId.set(conversation.id, conversation);
  }
  return sortConversations([...byId.values()]);
};

const agentSlice = createSlice({
  name: "agent",
  initialState,
  reducers: {
    clearAgentIdentity(state) {
      state.agentId = null;
      state.profile = null;
    },
    setAgentIdentity(
      state,
      action: PayloadAction<{ agentId: string; profile: AgentProfile }>,
    ) {
      state.agentId = action.payload.agentId;
      state.profile = action.payload.profile;
    },
    setAgentProfile(state, action: PayloadAction<AgentProfile>) {
      state.profile = action.payload;
    },
    setStatusFilter(state, action: PayloadAction<AgentConversationFilter>) {
      state.statusFilter = action.payload;
    },
    setConversations(state, action: PayloadAction<Conversation[]>) {
      state.conversations = sortConversations(action.payload);

      const allowedConversationIds = new Set(state.conversations.map((item) => item.id));
      if (
        state.selectedConversationId &&
        !allowedConversationIds.has(state.selectedConversationId)
      ) {
        state.selectedConversationId = null;
      }

      if (!state.selectedConversationId && state.conversations.length > 0) {
        state.selectedConversationId = state.conversations[0].id;
      }
    },
    upsertConversation(state, action: PayloadAction<Conversation>) {
      state.conversations = mergeConversations(state.conversations, [action.payload]);
      if (!state.selectedConversationId) {
        state.selectedConversationId = action.payload.id;
      }
    },
    selectConversation(state, action: PayloadAction<string | null>) {
      state.selectedConversationId = action.payload;
      if (action.payload) {
        state.unreadByConversation[action.payload] = 0;
      }
    },
    setConversationMessages(
      state,
      action: PayloadAction<{ conversationId: string; messages: Message[] }>,
    ) {
      const { conversationId, messages } = action.payload;
      state.messagesByConversation[conversationId] = sortMessages(messages);
      if (state.selectedConversationId === conversationId) {
        state.unreadByConversation[conversationId] = 0;
      }
    },
    upsertConversationMessage(state, action: PayloadAction<Message>) {
      const message = action.payload;
      const conversationId = message.conversation_id;
      const existing = state.messagesByConversation[conversationId] ?? [];
      state.messagesByConversation[conversationId] = mergeMessages(existing, [message]);
      if (state.selectedConversationId !== conversationId) {
        const currentUnread = state.unreadByConversation[conversationId] ?? 0;
        state.unreadByConversation[conversationId] = currentUnread + 1;
      }
    },
    resetAgentWorkspace(state) {
      state.conversations = [];
      state.selectedConversationId = null;
      state.messagesByConversation = {};
      state.unreadByConversation = {};
    },
  },
});

export const {
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
} = agentSlice.actions;

export default agentSlice.reducer;
