import type { AgentConversationFilter } from "../model/agentSlice";
import type { Conversation } from "../../../shared/types/chat";
import "./AgentConversationList.css";

const filterLabel: Record<AgentConversationFilter, string> = {
  all: "All",
  active: "Active",
  waiting: "Waiting",
  closed: "Closed",
};

const formatTime = (iso: string) => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.valueOf())) {
    return "";
  }
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

const filterOptions: AgentConversationFilter[] = [
  "active",
  "waiting",
  "closed",
  "all",
];

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
            : conversation.assigned_agent_id
              ? "Active"
              : "Waiting";
        const statusClass =
          conversation.status === "closed"
            ? "closed"
            : conversation.assigned_agent_id
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
              <time>{formatTime(conversation.updated_at)}</time>
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
