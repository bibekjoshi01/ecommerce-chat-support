import { FormEvent, useEffect, useRef } from "react";
import { FiSend, FiSlash } from "react-icons/fi";

import type { Conversation, Message } from "../../../shared/types/chat";
import "./AgentConversationThread.css";

const senderLabel = (senderType: Message["sender_type"]) => {
  if (senderType === "customer") {
    return "Customer";
  }
  if (senderType === "agent") {
    return "Agent";
  }
  if (senderType === "bot") {
    return "Bot";
  }
  return "System";
};

const formatTime = (iso: string) => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.valueOf())) {
    return "";
  }
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

interface AgentConversationThreadProps {
  selectedConversation: Conversation | null;
  messages: Message[];
  draft: string;
  isSendingMessage: boolean;
  isClosingConversation: boolean;
  isLoadingMessages: boolean;
  onDraftChange: (value: string) => void;
  onSendReply: () => void;
  onCloseConversation: () => void;
}

export const AgentConversationThread = ({
  selectedConversation,
  messages,
  draft,
  isSendingMessage,
  isClosingConversation,
  isLoadingMessages,
  onDraftChange,
  onSendReply,
  onCloseConversation,
}: AgentConversationThreadProps) => {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSendReply();
  };

  if (!selectedConversation) {
    return (
      <section className="agent-thread-panel">
        <div className="agent-thread-empty">
          Select a conversation to view and send replies.
        </div>
      </section>
    );
  }

  const isClosed = selectedConversation.status === "closed";

  return (
    <section className="agent-thread-panel">
      <header className="agent-thread-header">
        <div>
          <p className="agent-thread-kicker">Active Chat</p>
          <h2>{selectedConversation.customer_session_id}</h2>
        </div>

        <button
          className="agent-close-chat-button"
          type="button"
          onClick={onCloseConversation}
          disabled={isClosingConversation || isClosed}
        >
          <FiSlash aria-hidden="true" />
          {isClosed ? "Closed" : isClosingConversation ? "Closing..." : "Close chat"}
        </button>
      </header>

      <div className="agent-thread-messages">
        {isLoadingMessages && messages.length === 0 && (
          <div className="agent-thread-empty">Loading messages...</div>
        )}

        {!isLoadingMessages && messages.length === 0 && (
          <div className="agent-thread-empty">No messages yet in this chat.</div>
        )}

        {messages.map((message) => {
          const messageTone =
            message.sender_type === "agent"
              ? "agent-thread-bubble--agent"
              : message.sender_type === "customer"
                ? "agent-thread-bubble--customer"
                : "agent-thread-bubble--system";
          return (
            <article key={message.id} className={`agent-thread-bubble ${messageTone}`}>
              <div className="agent-thread-bubble-meta">
                <span>{senderLabel(message.sender_type)}</span>
                <time>{formatTime(message.created_at)}</time>
              </div>
              <p>{message.content}</p>
            </article>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      <form className="agent-thread-composer" onSubmit={onSubmit}>
        <input
          className="agent-thread-input"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder={isClosed ? "This chat is closed." : "Type your reply to customer..."}
          maxLength={4000}
          disabled={isSendingMessage || isClosed}
        />
        <button
          className="agent-thread-send"
          type="submit"
          disabled={isSendingMessage || isClosed || !draft.trim()}
        >
          <FiSend aria-hidden="true" />
          {isSendingMessage ? "Sending..." : "Reply"}
        </button>
      </form>
    </section>
  );
};
