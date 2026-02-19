export type ConversationStatus = "automated" | "agent" | "closed";
export type MessageSenderType = "customer" | "bot" | "agent" | "system";
export type MessageKind = "text" | "quick_reply" | "event";

export interface QuickQuestion {
  slug: string;
  question: string;
}

export interface Conversation {
  id: string;
  customer_session_id: string;
  status: ConversationStatus;
  assigned_agent_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_type: MessageSenderType;
  kind: MessageKind;
  content: string;
  metadata_json?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface ConversationBootstrapResponse {
  conversation: Conversation;
  quick_questions: QuickQuestion[];
  messages: Message[];
  show_talk_to_agent: boolean;
}

export interface ConversationMessagesResponse {
  conversation: Conversation;
  messages: Message[];
}

export interface BotExchangeResponse {
  conversation: Conversation;
  customer_message: Message;
  bot_message: Message;
  quick_questions: QuickQuestion[];
  show_talk_to_agent: boolean;
}
