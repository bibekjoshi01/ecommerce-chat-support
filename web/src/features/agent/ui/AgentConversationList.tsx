import type { AgentConversationFilter } from "../model/agentSlice";
import type { Conversation } from "../../../shared/types/chat";
import "./AgentConversationList.css";

const filterLabel: Record<AgentConversationFilter, string> = {
  all: "All",
  active: "Active",
  closed: "Closed",
};

const formatRelativeTime = (iso: string) => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.valueOf())) {
    return "";
  }

  const now = new Date();
  const isSameDay =
    parsed.getFullYear() === now.getFullYear() &&
    parsed.getMonth() === now.getMonth() &&
    parsed.getDate() === now.getDate();
  if (isSameDay) {
    return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  const diffMs = now.getTime() - parsed.getTime();
  const diffDays = Math.max(1, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
  if (diffDays < 30) {
    return diffDays === 1 ? "1 day ago" : `${diffDays} days ago`;
  }

  const diffMonths = Math.max(1, Math.floor(diffDays / 30));
  if (diffMonths < 12) {
    return diffMonths === 1 ? "1 month ago" : `${diffMonths} months ago`;
  }

  const diffYears = Math.max(1, Math.floor(diffMonths / 12));
  return diffYears === 1 ? "1 year ago" : `${diffYears} years ago`;
};

interface AgentConversationListProps {
  conversations: Conversation[];
  selectedConversationId: string | null;
  statusFilter: AgentConversationFilter;
  unreadByConversation: Record<string, number>;
  isLoading: boolean;
  onSelectConversation: (conversationId: string) => void;
  onFilterChange: (nextFilter: AgentConversationFilter) => void;
}

const filterOptions: AgentConversationFilter[] = ["active", "closed", "all"];

export const AgentConversationList = ({
  conversations,
  selectedConversationId,
  statusFilter,
  unreadByConversation,
  isLoading,
  onSelectConversation,
  onFilterChange,
}: AgentConversationListProps) => (
  <section className="agent-list-panel" aria-label="Agent conversation list">
    <div className="agent-list-header">
      <h2>Conversations</h2>
      <span>{conversations.length}</span>
    </div>

    <div className="agent-filter-row">
      {filterOptions.map((filter) => (
        <button
          key={filter}
          className={`agent-filter-chip ${statusFilter === filter ? "agent-filter-chip--active" : ""}`}
          type="button"
          onClick={() => onFilterChange(filter)}
        >
          {filterLabel[filter]}
        </button>
      ))}
    </div>

    <div className="agent-list-body">
      {isLoading && conversations.length === 0 && (
        <div className="agent-list-empty">Loading conversations...</div>
      )}

      {!isLoading && conversations.length === 0 && (
        <div className="agent-list-empty">
          No conversations for this filter yet.
        </div>
      )}

      {conversations.map((conversation) => {
        const unread = unreadByConversation[conversation.id] ?? 0;
        const statusLabel =
          conversation.status === "closed"
            ? "Closed"
            : conversation.status === "agent"
              ? conversation.assigned_agent_id
                ? "Active"
                : "Queue"
              : "Waiting";
        const statusClass =
          conversation.status === "closed"
            ? "closed"
            : conversation.status === "agent"
              ? "agent"
              : "automated";
        return (
          <button
            key={conversation.id}
            className={`agent-conversation-card ${
              selectedConversationId === conversation.id
                ? "agent-conversation-card--active"
                : ""
            }`}
            type="button"
            onClick={() => onSelectConversation(conversation.id)}
          >
            <div className="agent-conversation-row">
              <span className="agent-conversation-session">
                {conversation.customer_session_id.slice(0, 18)}
              </span>
              <time>{formatRelativeTime(conversation.updated_at)}</time>
            </div>

            <div className="agent-conversation-row">
              <span
                className={`agent-status-pill agent-status-pill--${statusClass}`}
              >
                {statusLabel}
              </span>

              {unread > 0 && <span className="agent-unread-pill">{unread}</span>}
            </div>
          </button>
        );
      })}
    </div>
  </section>
);
