const AGENT_ACCESS_TOKEN_KEY = "ecommerce-chat/agent-access-token";
const AGENT_EXPIRES_AT_KEY = "ecommerce-chat/agent-session-expires-at";
const AGENT_ID_KEY = "ecommerce-chat/agent-id";
const AGENT_NAME_KEY = "ecommerce-chat/agent-display-name";
const AGENT_USERNAME_KEY = "ecommerce-chat/agent-username";

export interface AgentSession {
  accessToken: string;
  expiresAt: string;
  agentId: string;
  displayName: string;
  username: string;
}

const isExpired = (expiresAt: string): boolean => {
  const parsed = new Date(expiresAt);
  if (Number.isNaN(parsed.valueOf())) {
    return true;
  }
  return parsed.getTime() <= Date.now();
};

export const clearStoredAgentSession = (): void => {
  localStorage.removeItem(AGENT_ACCESS_TOKEN_KEY);
  localStorage.removeItem(AGENT_EXPIRES_AT_KEY);
  localStorage.removeItem(AGENT_ID_KEY);
  localStorage.removeItem(AGENT_NAME_KEY);
  localStorage.removeItem(AGENT_USERNAME_KEY);
};

export const loadStoredAgentSession = (): AgentSession | null => {
  const accessToken = localStorage.getItem(AGENT_ACCESS_TOKEN_KEY);
  const expiresAt = localStorage.getItem(AGENT_EXPIRES_AT_KEY);
  const agentId = localStorage.getItem(AGENT_ID_KEY);
  const displayName = localStorage.getItem(AGENT_NAME_KEY);
  const username = localStorage.getItem(AGENT_USERNAME_KEY);

  if (!accessToken || !expiresAt || !agentId || !displayName || !username) {
    return null;
  }
  if (isExpired(expiresAt)) {
    clearStoredAgentSession();
    return null;
  }

  return {
    accessToken,
    expiresAt,
    agentId,
    displayName,
    username,
  };
};

export const saveStoredAgentSession = (session: AgentSession): AgentSession => {
  const normalized: AgentSession = {
    accessToken: session.accessToken,
    expiresAt: session.expiresAt,
    agentId: session.agentId,
    displayName: session.displayName.trim(),
    username: session.username.trim().toLowerCase(),
  };

  localStorage.setItem(AGENT_ACCESS_TOKEN_KEY, normalized.accessToken);
  localStorage.setItem(AGENT_EXPIRES_AT_KEY, normalized.expiresAt);
  localStorage.setItem(AGENT_ID_KEY, normalized.agentId);
  localStorage.setItem(AGENT_NAME_KEY, normalized.displayName);
  localStorage.setItem(AGENT_USERNAME_KEY, normalized.username);
  return normalized;
};

export const loadValidAgentAccessToken = (): string | null =>
  loadStoredAgentSession()?.accessToken ?? null;
