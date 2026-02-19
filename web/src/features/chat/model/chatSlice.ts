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

const isAgentConnectedNotice = (message: Message) =>
  message.sender_type === "system" &&
  message.kind === "event" &&
  message.content
    .trim()
    .toLowerCase()
    .endsWith("is connected. you can continue typing your message.");

const mergeMessages = (existing: Message[], incoming: Message[]) => {
  const byId = new Map(existing.map((message) => [message.id, message]));
  const existingConnectedNoticeContent = new Set(
    existing
      .filter((message) => isAgentConnectedNotice(message))
      .map((message) => message.content.trim()),
  );

  for (const message of incoming) {
    if (
      !byId.has(message.id) &&
      isAgentConnectedNotice(message) &&
      existingConnectedNoticeContent.has(message.content.trim())
    ) {
      continue;
    }
    byId.set(message.id, message);
    if (isAgentConnectedNotice(message)) {
      existingConnectedNoticeContent.add(message.content.trim());
    }
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
    setConversationMessages(
      state,
      action: PayloadAction<{ conversation: Conversation; messages: Message[] }>,
    ) {
      state.conversation = action.payload.conversation;
      state.messages = sortByCreatedAt(action.payload.messages);
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
  setConversationMessages,
  upsertConversation,
  upsertMessage,
} = chatSlice.actions;

export default chatSlice.reducer;
