const AGENT_ID_KEY = "ecommerce-chat/agent-id";
const AGENT_NAME_KEY = "ecommerce-chat/agent-display-name";

const fallbackAgentName = () => {
  const suffix = Math.random().toString(36).slice(2, 6).toUpperCase();
  return `Agent ${suffix}`;
};

export interface AgentIdentity {
  agentId: string;
  displayName: string;
}

export const loadStoredAgentIdentity = (): AgentIdentity | null => {
  const agentId = localStorage.getItem(AGENT_ID_KEY);
  const displayName = localStorage.getItem(AGENT_NAME_KEY);
  if (!agentId) {
    return null;
  }

  return {
    agentId,
    displayName: displayName?.trim() || fallbackAgentName(),
  };
};

export const saveStoredAgentIdentity = (
  identity: AgentIdentity,
): AgentIdentity => {
  const cleanedName = identity.displayName.trim() || fallbackAgentName();
  localStorage.setItem(AGENT_ID_KEY, identity.agentId);
  localStorage.setItem(AGENT_NAME_KEY, cleanedName);
  return {
    agentId: identity.agentId,
    displayName: cleanedName,
  };
};

export const clearStoredAgentIdentity = (): void => {
  localStorage.removeItem(AGENT_ID_KEY);
  localStorage.removeItem(AGENT_NAME_KEY);
};

export const createDefaultAgentDisplayName = (): string => fallbackAgentName();
