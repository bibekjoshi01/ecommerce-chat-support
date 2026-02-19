const SESSION_KEY = "ecommerce-chat/customer-session-id";

const fallbackSessionId = () =>
  `cust_${Math.random().toString(36).slice(2, 14)}${Date.now().toString(36)}`;

export const loadOrCreateSessionId = (): string => {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) {
    return existing;
  }

  const generated =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? `cust_${crypto.randomUUID().replaceAll("-", "").slice(0, 24)}`
      : fallbackSessionId();

  localStorage.setItem(SESSION_KEY, generated);
  return generated;
};
