import { PayloadAction, createSlice } from "@reduxjs/toolkit";

import type {
  BotExchangeResponse,
  Conversation,
  ConversationBootstrapResponse,
  Message,
  QuickQuestion,
} from "../../../shared/types/chat";

interface ChatState {
  sessionId: string | null;
  conversation: Conversation | null;
  messages: Message[];
  quickQuestions: QuickQuestion[];
}

const initialState: ChatState = {
  sessionId: null,
  conversation: null,
  messages: [],
  quickQuestions: [],
};

const sortByCreatedAt = (messages: Message[]) =>
  [...messages].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

const mergeMessages = (existing: Message[], incoming: Message[]) => {
  const byId = new Map(existing.map((message) => [message.id, message]));
  for (const message of incoming) {
    byId.set(message.id, message);
  }
  return sortByCreatedAt([...byId.values()]);
};

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    setSessionId(state, action: PayloadAction<string>) {
      state.sessionId = action.payload;
    },
    hydrateFromBootstrap(
      state,
      action: PayloadAction<ConversationBootstrapResponse>,
    ) {
      state.conversation = action.payload.conversation;
      state.messages = sortByCreatedAt(action.payload.messages);
      state.quickQuestions = action.payload.quick_questions;
    },
    appendExchange(state, action: PayloadAction<BotExchangeResponse>) {
      state.conversation = action.payload.conversation;
      const incoming = [action.payload.customer_message];
      if (action.payload.bot_message) {
        incoming.push(action.payload.bot_message);
      }
      state.messages = mergeMessages(state.messages, incoming);
      state.quickQuestions = action.payload.quick_questions;
    },
    upsertConversation(state, action: PayloadAction<Conversation>) {
      state.conversation = action.payload;
    },
    upsertMessage(state, action: PayloadAction<Message>) {
      state.messages = mergeMessages(state.messages, [action.payload]);
    },
  },
});

export const {
  appendExchange,
  hydrateFromBootstrap,
  setSessionId,
  upsertConversation,
  upsertMessage,
} = chatSlice.actions;

export default chatSlice.reducer;
