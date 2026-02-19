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
      state.messages = mergeMessages(state.messages, [
        action.payload.customer_message,
        action.payload.bot_message,
      ]);
      state.quickQuestions = action.payload.quick_questions;
    },
  },
});

export const { appendExchange, hydrateFromBootstrap, setSessionId } =
  chatSlice.actions;

export default chatSlice.reducer;
