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

const senderPriority: Record<Message["sender_type"], number> = {
  customer: 0,
  agent: 1,
  bot: 2,
  system: 3,
};

const compareMessages = (a: Message, b: Message) => {
  const timeDelta =
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  if (timeDelta !== 0) {
    return timeDelta;
  }
  const senderDelta = senderPriority[a.sender_type] - senderPriority[b.sender_type];
  if (senderDelta !== 0) {
    return senderDelta;
  }
  return a.id.localeCompare(b.id);
};

const sortByCreatedAt = (messages: Message[]) => [...messages].sort(compareMessages);

const isAgentConnectedNotice = (message: Message) =>
  message.sender_type === "system" &&
  message.kind === "event" &&
  message.content
    .trim()
    .toLowerCase()
    .endsWith("is connected. you can continue typing your message.");

const isSuppressedSystemNotice = (message: Message) => {
  if (message.sender_type !== "system" || message.kind !== "event") {
    return false;
  }
  const normalized = message.content.trim().toLowerCase();
  return (
    normalized.includes("agent disconnected") &&
    normalized.includes("reconnecting you to another agent")
  );
};

const mergeMessages = (existing: Message[], incoming: Message[]) => {
  const byId = new Map(existing.map((message) => [message.id, message]));
  const existingConnectedNoticeContent = new Set(
    existing
      .filter((message) => isAgentConnectedNotice(message))
      .map((message) => message.content.trim()),
  );

  for (const message of incoming) {
    if (!byId.has(message.id) && isSuppressedSystemNotice(message)) {
      continue;
    }
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
      state.messages = sortByCreatedAt(
        action.payload.messages.filter(
          (message) => !isSuppressedSystemNotice(message),
        ),
      );
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
      state.messages = sortByCreatedAt(
        action.payload.messages.filter(
          (message) => !isSuppressedSystemNotice(message),
        ),
      );
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
