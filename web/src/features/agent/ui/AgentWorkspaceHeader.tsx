import { FiRefreshCw, FiRotateCw } from "react-icons/fi";

import type { AgentProfile } from "../../../shared/types/chat";
import "./AgentWorkspaceHeader.css";

interface AgentWorkspaceHeaderProps {
  profile: AgentProfile | null;
  isRealtimeConnected: boolean;
  isRefreshingConversations: boolean;
  onRefresh: () => void;
  onReconnect: () => void;
}

export const AgentWorkspaceHeader = ({
  profile,
  isRealtimeConnected,
  isRefreshingConversations,
  onRefresh,
  onReconnect,
}: AgentWorkspaceHeaderProps) => (
  <section className="agent-workspace-header">
    <div>
      <p className="agent-workspace-kicker">Agent Console</p>
      <h1>Live Support Queue</h1>
      <p className="agent-workspace-subtitle">
        Manage assigned chats, respond quickly, and close conversations cleanly.
      </p>
    </div>

    <div className="agent-workspace-controls">
      <div className="agent-identity-pill">
        <span className="agent-identity-name">
          {profile?.display_name || "Initializing agent..."}
        </span>
        <span
          className={`agent-realtime-badge ${
            isRealtimeConnected ? "agent-realtime-badge--online" : ""
          }`}
        >
          {isRealtimeConnected ? "Realtime: connected" : "Realtime: reconnecting"}
        </span>
      </div>

      <div className="agent-control-buttons">
        <button
          className="agent-control-button"
          type="button"
          onClick={onRefresh}
          disabled={isRefreshingConversations}
        >
          <FiRefreshCw aria-hidden="true" />
          {isRefreshingConversations ? "Refreshing..." : "Refresh"}
        </button>

        <button className="agent-control-button" type="button" onClick={onReconnect}>
          <FiRotateCw aria-hidden="true" />
          Re-register
        </button>
      </div>
    </div>
  </section>
);
