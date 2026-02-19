import { Link } from "react-router-dom";

import { AgentConversationList } from "./AgentConversationList";
import { AgentConversationThread } from "./AgentConversationThread";
import { AgentWorkspaceHeader } from "./AgentWorkspaceHeader";
import { useAgentWorkspaceController } from "../model/useAgentWorkspaceController";
import "./AgentWorkspace.css";

export const AgentWorkspace = () => {
  const {
    conversations,
    draft,
    isClosingConversation,
    isLoadingMessages,
    isRealtimeConnected,
    isRefreshingConversations,
    isRegisteringAgent,
    isSendingMessage,
    profile,
    selectedConversation,
    selectedConversationId,
    selectedConversationMessages,
    setDraft,
    setFilter,
    statusFilter,
    uiError,
    unreadByConversation,
    closeSelectedConversation,
    reconnectAgent,
    refreshConversations,
    selectConversationById,
    sendReply,
  } = useAgentWorkspaceController();

  return (
    <div className="agent-page">
      <header className="site-header">
        <Link className="brand" to="/">
          CommerceCare
        </Link>
        <nav className="top-nav">
          <Link className="top-nav-link" to="/">
            Customer Home
          </Link>
        </nav>
      </header>

      <main className="agent-workspace-shell">
        <AgentWorkspaceHeader
          isRealtimeConnected={isRealtimeConnected}
          isRefreshingConversations={isRefreshingConversations}
          profile={profile}
          onReconnect={reconnectAgent}
          onRefresh={() => void refreshConversations()}
        />

        {uiError && <div className="agent-workspace-error">{uiError}</div>}

        <div className="agent-workspace-grid">
          <AgentConversationList
            conversations={conversations}
            isLoading={isRefreshingConversations || isRegisteringAgent}
            onSelectConversation={selectConversationById}
            selectedConversationId={selectedConversationId}
            statusFilter={statusFilter}
            unreadByConversation={unreadByConversation}
            onFilterChange={setFilter}
          />

          <AgentConversationThread
            draft={draft}
            isClosingConversation={isClosingConversation}
            isLoadingMessages={isLoadingMessages}
            isSendingMessage={isSendingMessage}
            messages={selectedConversationMessages}
            onCloseConversation={() => void closeSelectedConversation()}
            onDraftChange={setDraft}
            onSendReply={() => void sendReply()}
            selectedConversation={selectedConversation}
          />
        </div>
      </main>
    </div>
  );
};
