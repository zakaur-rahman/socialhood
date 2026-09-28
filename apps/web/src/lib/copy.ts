/** UI copy from §4.7 (UX-COPY-01). Plain, specific, no apologies. */
import { ApiError } from "@/lib/api/errors";

export const SUPPORT_EMAIL = "support@socialhood.com";

export function errorMessage(error: unknown): string {
  const apiError = error instanceof ApiError ? error : null;
  if (apiError?.code === "network" || (typeof navigator !== "undefined" && !navigator.onLine)) {
    return "You're offline. Reconnect and try again.";
  }
  if (apiError && apiError.status >= 400 && apiError.status < 500 && apiError.detail) {
    return apiError.detail;
  }
  const code = apiError?.requestId ? ` with code ${apiError.requestId}` : "";
  return `Something went wrong on our side. Try again. If it keeps happening, email ${SUPPORT_EMAIL}${code}.`;
}

export const emptyStates = {
  notifications: {
    title: "No notifications",
    body: "We'll tell you when something needs your attention.",
  },
  connections: {
    title: "Connect an account",
    body: "Messages from Instagram and WhatsApp will appear here.",
  },
} as const;

// ---- connecting accounts (F-03, §4.7)

export type ConnectResult =
  | { kind: "success"; message: string }
  | { kind: "error"; message: string; retry: boolean };

/** Codes the OAuth callback puts in ?error= (F-03 edge cases). */
export const CONNECT_ERRORS = [
  "access_denied",
  "state_invalid",
  "ig_not_professional",
  "account_in_use",
  "connect_failed",
  "quota_exceeded",
] as const;
export type ConnectError = (typeof CONNECT_ERRORS)[number];

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** The toast for the ?connected= / ?error= the callback redirected with, or null for none. */
export function connectResult(params: URLSearchParams, username?: string | null): ConnectResult | null {
  if (params.get("connected") === "instagram") {
    return { kind: "success", message: username ? `Instagram connected: @${username}` : "Instagram connected" };
  }
  const error = params.get("error");
  if (!error) return null;
  switch (error as ConnectError) {
    case "access_denied":
      return { kind: "error", message: "Connection cancelled", retry: false };
    case "state_invalid":
      return { kind: "error", message: "That connection link expired.", retry: true };
    case "ig_not_professional":
      return {
        kind: "error",
        message:
          "Only Instagram business and creator accounts can connect. Switch the account type in the Instagram app, then try again.",
        retry: true,
      };
    case "account_in_use":
      return {
        kind: "error",
        message: "This account is connected to another Social Hood workspace. Disconnect it there first.",
        retry: false,
      };
    case "quota_exceeded": {
      const limit = Number(params.get("limit"));
      return {
        kind: "error",
        message: Number.isFinite(limit) && limit > 0
          ? `Your plan includes ${plural(limit, "Instagram account", "Instagram accounts")}.`
          : "Your plan's Instagram account limit is reached.",
        retry: false,
      };
    }
    case "connect_failed":
    default:
      return { kind: "error", message: "Instagram didn't respond. Try again.", retry: true };
  }
}

export const accountStatusLabel = {
  active: "Connected",
  needs_reconnect: "Needs reconnecting",
  error: "Error",
  disconnected: "Disconnected",
} as const;

export function reconnectBanner(username: string | null | undefined): string {
  return username
    ? `Reconnect @${username} to keep receiving messages`
    : "Reconnect your Instagram account to keep receiving messages";
}

export function greeting(now: Date, firstName?: string | null): string {
  const hour = now.getHours();
  const part = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return firstName ? `${part}, ${firstName}` : part;
}
