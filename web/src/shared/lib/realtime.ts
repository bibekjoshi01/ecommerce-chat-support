const DEFAULT_CUSTOMER_API_BASE_URL = "/api/v1/customer";
const DEFAULT_REALTIME_WS_PATH = "/api/v1/realtime/ws";

const resolveWsBase = (): URL => {
  const explicitWsUrl = import.meta.env.VITE_REALTIME_WS_URL as string | undefined;
  if (explicitWsUrl) {
    return new URL(explicitWsUrl, window.location.origin);
  }

  const customerApiBaseUrl =
    (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
    DEFAULT_CUSTOMER_API_BASE_URL;

  if (customerApiBaseUrl.startsWith("http://")) {
    const url = new URL(customerApiBaseUrl);
    return new URL(
      `${url.pathname.replace(/\/customer\/?$/, "")}/realtime/ws`,
      `ws://${url.host}`,
    );
  }

  if (customerApiBaseUrl.startsWith("https://")) {
    const url = new URL(customerApiBaseUrl);
    return new URL(
      `${url.pathname.replace(/\/customer\/?$/, "")}/realtime/ws`,
      `wss://${url.host}`,
    );
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const origin = `${protocol}//${window.location.host}`;
  return new URL(DEFAULT_REALTIME_WS_PATH, origin);
};

export const buildRealtimeWsUrl = (
  params: Record<string, string | undefined>,
): string => {
  const url = resolveWsBase();
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (!value) {
      continue;
    }
    searchParams.set(key, value);
  }
  url.search = searchParams.toString();
  return url.toString();
};
