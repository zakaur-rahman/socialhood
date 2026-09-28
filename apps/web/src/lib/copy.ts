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
} as const;

export function greeting(now: Date, firstName?: string | null): string {
  const hour = now.getHours();
  const part = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return firstName ? `${part}, ${firstName}` : part;
}
