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
  requested_agent_at?: string | null;
  closed_at?: string | null;
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
  bot_message: Message | null;
  quick_questions: QuickQuestion[];
  show_talk_to_agent: boolean;
}

export interface AgentProfile {
  id: string;
  display_name: string;
  presence: "online" | "offline";
  max_active_chats: number;
  created_at: string;
  updated_at: string;
}

export interface AgentConversationListResponse {
  items: Conversation[];
}

export interface AgentConversationMessagesResponse {
  conversation: Conversation;
  messages: Message[];
}

export interface AgentMessageExchangeResponse {
  conversation: Conversation;
  message: Message;
}

export interface AgentCloseConversationResponse {
  conversation: Conversation;
  system_message: Message | null;
}

export interface RealtimeEnvelope<TPayload = unknown> {
  event: string;
  channel?: string;
  payload: TPayload;
  sent_at: string;
}
