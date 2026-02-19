import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import type { Message } from "../../../shared/types/chat";
import { useCustomerChatController } from "../model/useCustomerChatController";

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
});

const senderLabel = (senderType: Message["sender_type"]) =>
  senderType === "customer" ? "You" : "Support";

const formatTime = (iso: string) => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.valueOf())) {
    return "";
  }
  return timeFormatter.format(parsed);
};

export const CustomerChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const {
    conversation,
    draft,
    isAssistantTyping,
    isConversationClosed,
    isSending,
    isStartingConversation,
    messages,
    quickQuestions,
    setDraft,
    sendDraft,
    sendQuickQuestion,
    startNewConversation,
    uiError,
  } = useCustomerChatController();

  const canSend = !!conversation && !isConversationClosed && !isSending;

  const inputPlaceholder = useMemo(() => {
    if (!conversation) {
      return "Starting chat...";
    }
    if (isConversationClosed) {
      return "Chat ended. Start a new conversation.";
    }
    return "Type your message...";
  }, [conversation, isConversationClosed]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [isAssistantTyping, isOpen, messages]);

  const handleSend = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await sendDraft();
  };

  return (
    <div className="chat-widget-root">
      {isOpen && (
        <section className="chat-panel" aria-label="Customer support chat">
          <header className="chat-panel-header">
            <div>
              <p className="chat-kicker">Live customer support</p>
              <h2>Need help with your order?</h2>
            </div>
            <div className="chat-panel-actions">
              <button
                className="chat-mini-button"
                type="button"
                onClick={() => void startNewConversation()}
                disabled={isStartingConversation}
              >
                New chat
              </button>
              <button
                className="chat-close-button"
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close chat"
              >
                ✕
              </button>
            </div>
          </header>

          {uiError && <div className="chat-error">{uiError}</div>}

          <div className="chat-messages">
            {isStartingConversation && !conversation && (
              <div className="chat-empty">Connecting you with support...</div>
            )}

            {!isStartingConversation && messages.length === 0 && (
              <div className="chat-empty">
                Ask anything about order status, delivery, or returns.
              </div>
            )}

            {messages.map((message) => {
              const tone =
                message.sender_type === "customer" ? "bubble--customer" : "bubble--support";

              return (
                <article className={`bubble ${tone}`} key={message.id}>
                  <div className="bubble-meta">
                    <span>{senderLabel(message.sender_type)}</span>
                    <time>{formatTime(message.created_at)}</time>
                  </div>
                  <p>{message.content}</p>
                </article>
              );
            })}

            {isAssistantTyping && (
              <article className="bubble bubble--support bubble--typing">
                <div className="bubble-meta">
                  <span>Support</span>
                  <time>typing...</time>
                </div>
                <p className="typing-dots">
                  <span />
                  <span />
                  <span />
                </p>
              </article>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="chat-quick-questions">
            {quickQuestions.map((quickQuestion) => (
              <button
                key={quickQuestion.slug}
                className="quick-question-button"
                type="button"
                disabled={!canSend}
                onClick={() => void sendQuickQuestion(quickQuestion.slug)}
              >
                {quickQuestion.question}
              </button>
            ))}
          </div>

          <form className="chat-composer" onSubmit={handleSend}>
            <input
              className="chat-input"
              value={draft}
              maxLength={4000}
              disabled={!canSend}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={inputPlaceholder}
              aria-label="Customer message"
            />
            <button
              className="chat-send"
              type="submit"
              disabled={!canSend || !draft.trim()}
            >
              {isSending ? "Sending..." : "Send"}
            </button>
          </form>
        </section>
      )}

      <button
        className="chat-launcher"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-label={isOpen ? "Close support chat" : "Open support chat"}
      >
        <span className="chat-launcher-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
          </svg>
        </span>
        <span className="chat-launcher-label">
          {isOpen ? "Close chat" : "Chat with us"}
        </span>
      </button>
    </div>
  );
};
