import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { FiMessageCircle, FiRefreshCw, FiSend, FiX } from "react-icons/fi";

import type { Message } from "../../../shared/types/chat";
import { useCustomerChatController } from "../model/useCustomerChatController";
import "./CustomerChatWidget.css";

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
    escalateToAgent,
    isAgentMode,
    isAssistantTyping,
    isAutomatedMode,
    isConversationClosed,
    isEscalatingToAgent,
    isRealtimeConnected,
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

  const canSendAgentMessage =
    !!conversation && isAgentMode && !isConversationClosed && !isSending;
  const canUseQuickQuestions =
    !!conversation && isAutomatedMode && !isConversationClosed && !isSending;
  const canEscalate =
    !!conversation &&
    isAutomatedMode &&
    !isConversationClosed &&
    !isEscalatingToAgent;

  const inputPlaceholder = useMemo(() => {
    if (isConversationClosed) {
      return "Chat ended. Start a new conversation.";
    }
    return "Write your message ...";
  }, [isConversationClosed]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
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
              {conversation && (
                <p className="chat-live-indicator">
                  {isRealtimeConnected ? "Live" : "Reconnecting..."}
                </p>
              )}
            </div>
            <div className="chat-panel-actions">
              <button
                className="chat-mini-button"
                type="button"
                onClick={() => void startNewConversation()}
                disabled={isStartingConversation}
              >
                <FiRefreshCw aria-hidden="true" />
                New chat
              </button>
              <button
                className="chat-close-button"
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close chat"
              >
                <FiX aria-hidden="true" />
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
                Choose one quick question to get an instant automated reply.
              </div>
            )}

            {messages.map((message) => {
              const tone =
                message.sender_type === "customer"
                  ? "bubble--customer"
                  : "bubble--support";

              return (
                <article className={`bubble ${tone}`} key={message.id}>
                  <div className="bubble-meta">
                    <span>{senderLabel(message.sender_type)}</span>
                    <time>{formatTime(message.created_at)}</time>
                  </div>
                  <p>{message.content}</p>
                  {isAutomatedMode && message.sender_type === "bot" && (
                    <div className="bubble-action-row">
                      <button
                        className="bubble-escalate-button"
                        type="button"
                        onClick={() => void escalateToAgent()}
                        disabled={!canEscalate}
                      >
                        Talk to agent
                      </button>
                    </div>
                  )}
                </article>
              );
            })}

            {isAssistantTyping && (
              <article className="bubble bubble--support bubble--typing">
                <div className="bubble-meta">
                  <time>typing...</time>
                </div>
                <p className="typing-dots">
                  <span />
                  <span />
                  <span />
                </p>
              </article>
            )}

            {isAutomatedMode && quickQuestions.length > 0 && (
              <div className="chat-inline-quick-questions">
                {quickQuestions.map((quickQuestion) => (
                  <button
                    key={quickQuestion.slug}
                    className="quick-question-button"
                    type="button"
                    disabled={!canUseQuickQuestions}
                    onClick={() => void sendQuickQuestion(quickQuestion.slug)}
                  >
                    {quickQuestion.question}
                  </button>
                ))}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {isAgentMode ? (
            <form className="chat-composer" onSubmit={handleSend}>
              <input
                className="chat-input"
                value={draft}
                maxLength={4000}
                disabled={!canSendAgentMessage}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={inputPlaceholder}
                aria-label="Customer message"
              />
              <button
                className="chat-send"
                type="submit"
                disabled={!canSendAgentMessage || !draft.trim()}
              >
                <FiSend aria-hidden="true" />
                {isSending ? "Sending..." : "Send"}
              </button>
            </form>
          ) : (
            <div className="chat-mode-footer">
              <p>Need personalized help from a human?</p>
              <button
                className="chat-escalate-button"
                type="button"
                onClick={() => void escalateToAgent()}
                disabled={!canEscalate}
              >
                {isEscalatingToAgent ? "Connecting..." : "Talk to agent"}
              </button>
            </div>
          )}
        </section>
      )}

      <button
        className="chat-launcher"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-label={isOpen ? "Close support chat" : "Open support chat"}
      >
        <span className="chat-launcher-icon" aria-hidden="true">
          <FiMessageCircle />
        </span>
        <span className="chat-launcher-label">
          {isOpen ? "Close chat" : "Chat with us"}
        </span>
      </button>
    </div>
  );
};
