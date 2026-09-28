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
  inboxNoConversations: {
    title: "No conversations yet",
    body: "New messages appear here as they arrive.",
  },
  inboxNothingSelected: {
    title: "Pick a conversation",
    body: "Choose someone on the left to start replying.",
  },
  scheduled: {
    title: "No scheduled messages",
    body: "Schedule a reply from any conversation's composer.",
  },
} as const;

/** "All caught up" when a view or search has no results (§4.7). */
export function inboxFilterEmpty(what: string): { title: string; body: string } {
  return { title: "All caught up", body: `Nothing matches "${what}" right now.` };
}

// ---- sending (§4.7 error codes, F-07)

type SendContext = {
  platform: "instagram" | "whatsapp";
  /** @username on Instagram; the display name or number on WhatsApp. */
  handle?: string | null;
};

export type SendFailure = {
  message: string;
  /** Retry makes sense for this failure (§4.7 "Action"). */
  retry: boolean;
  /** Reconnect the account first. */
  reconnect?: boolean;
  /** WhatsApp outside the window: send a template instead. */
  chooseTemplate?: boolean;
};

const PLATFORM_NAME = { instagram: "Instagram", whatsapp: "WhatsApp" } as const;

/**
 * The reason under a failed bubble, from the message's error code (message.error) or the
 * send request's ApiError. Unknown codes fall back to the platform's own message.
 */
export function sendFailure(
  error: { code: string; message?: string | null; requestId?: string | null },
  context: SendContext,
): SendFailure {
  const name = PLATFORM_NAME[context.platform];
  const handle = context.handle ? (context.platform === "instagram" ? `@${context.handle}` : context.handle) : "This account";
  const detail = error.message?.trim();
  switch (error.code) {
    case "network":
    case "offline":
      return { message: "You're offline. Reconnect to send messages.", retry: true };
    case "reply_window_closed":
      return context.platform === "whatsapp"
        ? {
            message:
              "WhatsApp allows free-form replies for 24 hours after the customer's last message. Send an approved template instead.",
            retry: false,
            chooseTemplate: true,
          }
        : { message: "Instagram allows replies for 24 hours after the customer's last message.", retry: false };
    case "account_needs_reconnect":
      return { message: `${handle} needs reconnecting before you can send from it.`, retry: false, reconnect: true };
    case "capability_unavailable":
      return detail && /permission/i.test(detail)
        ? {
            message: `${handle} didn't give Social Hood permission for this. Reconnect to allow it.`,
            retry: false,
            reconnect: true,
          }
        : { message: `${name} doesn't support this.`, retry: false };
    case "recipient_unavailable":
      return { message: "This person can't receive messages right now.", retry: false };
    case "platform_rate_limited":
      return { message: `${name} is limiting messages from this account. Try again in a few minutes.`, retry: true };
    case "platform_unavailable":
      return { message: `${name} didn't respond.`, retry: true };
    case "platform_rejected":
      return { message: detail ? `${name} rejected this: ${detail}` : `${name} rejected this.`, retry: false };
    case "delivery_unknown":
      return {
        message: `We couldn't confirm this was delivered. Check the chat in ${name} before retrying.`,
        retry: true,
      };
    case "internal": {
      const code = error.requestId ? ` with code ${error.requestId}` : "";
      return {
        message: `Something went wrong on our side. Try again. If it keeps happening, email ${SUPPORT_EMAIL}${code}.`,
        retry: true,
      };
    }
    default:
      // quota_exceeded, entitlement_required, unsupported_media, validation_error: the API's detail
      // already names the limit or field.
      return { message: detail || `${name} didn't accept this message.`, retry: false };
  }
}

/** Composer notices for reply-window states (F-07, UX-INB-07). */
export const composerCopy = {
  humanAgent: (closesIn: string) => `Replying with Human Agent tag. Window closes in ${closesIn}.`,
  closed: (name: string, lastMessage: string | null) =>
    `You can reply after ${name} messages again.${lastMessage ? ` Last message ${lastMessage}.` : ""}`,
  templateOnly: "The 24-hour window has closed. Send an approved template to restart the conversation.",
  needsReconnect: (handle: string) => `${handle} needs reconnecting before you can send from it.`,
  disconnected: (handle: string) => `${handle} is disconnected. Reconnect it to reply.`,
} as const;

/** F-04: Embedded Signup finished and the API stored the number. */
export function whatsappConnected(displayName: string | null | undefined, number: string | null | undefined): string {
  if (displayName && number) return `WhatsApp connected: ${displayName} (${number})`;
  return `WhatsApp connected: ${displayName ?? number ?? "your number"}`;
}

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
