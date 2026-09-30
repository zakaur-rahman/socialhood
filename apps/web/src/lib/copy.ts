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
  automations: {
    title: "Reply automatically",
    body: 'Send a DM when someone writes or comments a keyword like "price" or "link". Start from a template in a minute.',
  },
  automationsFiltered: {
    title: "No automations match",
    body: "Try another search or clear the filters.",
  },
  automationRuns: {
    title: "No runs yet",
    body: "Each time this automation answers someone, it shows here.",
  },
  knowledge: {
    title: "Teach the AI your business",
    body: "Add prices, shipping and FAQs so suggested replies are accurate.",
  },
  knowledgeGaps: {
    title: "No unanswered questions",
    body: "When customers ask something your knowledge doesn't cover, it shows up here.",
  },
  comments: {
    title: "No posts yet",
    body: "Your Instagram posts and their comments appear here after you connect.",
  },
  schedule: {
    title: "Plan your posts",
    body: "Drag drafts onto the calendar, or set posting times and add posts to your queue.",
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
    case "platform_rejected": {
      // A failed send stored by the server already carries the whole sentence.
      const prefix = `${name} rejected this`;
      if (detail?.startsWith(prefix)) return { message: detail, retry: false };
      return { message: detail ? `${prefix}: ${detail}` : `${prefix}.`, retry: false };
    }
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

// ---- AI and knowledge (P5, §4.7)

const count = new Intl.NumberFormat("en-US");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** A calendar date from the API ("2026-10-01") as "1 Oct", with the year when it isn't this one. */
export function shortDate(value: string, now: Date = new Date()): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const label = `${day} ${MONTHS[month - 1]}`;
  return year === now.getFullYear() ? label : `${label} ${year}`;
}

/** quota_exceeded for AI credits (FR-AI-05). */
export function aiCreditsExhausted(limit: number, resetsOn: string | null | undefined, now?: Date): string {
  const reset = resetsOn ? ` They reset on ${shortDate(resetsOn, now)}.` : "";
  return `You've used all ${count.format(limit)} AI credits for this month.${reset}`;
}

/** quota_exceeded for knowledge (F-14). */
export function knowledgeLimitReached(limit: number | null | undefined): string {
  return limit ? `Your plan includes ${count.format(limit)} characters of knowledge.` : "Your plan's knowledge limit is reached.";
}

export const aiCopy = {
  autoIsPro: "Auto mode is part of Pro.",
  businessDescriptionHint: "Two or three sentences about what you sell and who buys it.",
  notInKnowledge: "Not in your knowledge",
  drafting: "Drafting a reply…",
} as const;

// ---- billing (P8: F-15, UX-SCR-07, FR-BIL-02…06, §4.7 402 codes)

export type PlanName = "free" | "pro" | "max";

export const PLAN_NAME: Record<PlanName, string> = { free: "Free", pro: "Pro", max: "Max" };

function counted(n: number, one: string, many: string): string {
  return `${count.format(n)} ${n === 1 ? one : many}`;
}

type LimitCopy = {
  /** The upgrade dialog's title when this limit is reached (quota_exceeded). */
  limitTitle: string;
  /** What a limit of n includes: "3 active automations". */
  includes: (n: number) => string;
  /** What a plan without a limit has no limit on: "active automations". */
  unlimited: string;
};

/** Copy for each §1.7 entitlement with a number (C-049: a 402 carries its key and limit). */
const LIMIT_COPY: Record<string, LimitCopy> = {
  active_automations: {
    limitTitle: "Automation limit reached",
    includes: (n) => counted(n, "active automation", "active automations"),
    unlimited: "active automations",
  },
  accounts_per_platform: {
    limitTitle: "Account limit reached",
    includes: (n) => `${counted(n, "account", "accounts")} per platform`,
    unlimited: "connected accounts",
  },
  knowledge_characters: {
    limitTitle: "Knowledge limit reached",
    includes: (n) => `${count.format(n)} characters of knowledge`,
    unlimited: "knowledge",
  },
  scheduled_posts_monthly: {
    limitTitle: "Scheduled post limit reached",
    includes: (n) => `${counted(n, "scheduled post", "scheduled posts")} a month`,
    unlimited: "scheduled posts",
  },
  pending_scheduled_messages: {
    limitTitle: "Scheduled message limit reached",
    includes: (n) => `${counted(n, "scheduled message", "scheduled messages")} waiting to send`,
    unlimited: "scheduled messages",
  },
  members: {
    limitTitle: "Member limit reached",
    includes: (n) => counted(n, "member", "members"),
    unlimited: "members",
  },
  ai_credits_monthly: {
    limitTitle: "AI credits used up",
    includes: (n) => `${count.format(n)} AI credits a month`,
    unlimited: "AI credits",
  },
  comment_intelligence_posts: {
    limitTitle: "Comment analysis limit reached",
    includes: (n) => `comment analysis on the ${counted(n, "most recent post", "most recent posts")}`,
    unlimited: "comment analysis",
  },
  message_history_days: {
    limitTitle: "Message history limit reached",
    includes: (n) => `${counted(n, "day", "days")} of message history`,
    unlimited: "message history",
  },
};

/** Features a plan has or lacks (entitlement_required, §4.7 "{Feature} is part of Pro."). */
const FEATURE_COPY: Record<string, { feature: string; body: string }> = {
  ai_modes: {
    feature: "Auto mode",
    body: "On Pro, the AI can answer customers on its own when it's confident and the answer is in your knowledge.",
  },
  ai_reply_automations: {
    feature: "AI replies in automations",
    body: "On Pro, an automation can answer with AI from your knowledge instead of a fixed message.",
  },
};

/** What a limit of n on this §1.7 key includes, e.g. "3 active automations"; null for other keys. */
export function limitText(key: string, limit: number): string | null {
  return LIMIT_COPY[key]?.includes(limit) ?? null;
}

/** "Free includes 3 active automations." (F-15); without the plan, "Your plan includes …" (§4.7). */
export function planIncludes(key: string, limit: number, plan?: PlanName | null): string | null {
  const copy = LIMIT_COPY[key];
  if (!copy) return null;
  return `${plan ? PLAN_NAME[plan] : "Your plan"} includes ${copy.includes(limit)}.`;
}

/** What another plan offers for the same key: "Pro includes 50 active automations." */
export function planOffers(key: string, value: number | null, plan: PlanName): string | null {
  const copy = LIMIT_COPY[key];
  if (!copy) return null;
  return value === null
    ? `${PLAN_NAME[plan]} has no limit on ${copy.unlimited}.`
    : `${PLAN_NAME[plan]} includes ${copy.includes(value)}.`;
}

export type UpgradeCopyInput = {
  code: "entitlement_required" | "quota_exceeded";
  entitlement?: string | null;
  limit?: number | null;
  detail?: string | null;
};

/**
 * The upgrade dialog's title and first sentence for a 402 (§4.7): entitlement_required says
 * "{Feature} is part of Pro."; quota_exceeded names the limit, and for AI credits when they reset.
 */
export function upgradeCopy(
  input: UpgradeCopyInput,
  context: { plan?: PlanName | null; resetsOn?: string | null; now?: Date } = {},
): { title: string; body: string } {
  const key = input.entitlement ?? "";
  if (input.code === "entitlement_required") {
    const feature = FEATURE_COPY[key];
    if (feature) return { title: `${feature.feature} is part of Pro`, body: feature.body };
    const named = input.detail?.match(/^(.+?) is part of Pro\.?$/);
    if (named) return { title: `${named[1]} is part of Pro`, body: "Upgrade to Pro to use it." };
    return { title: "This is part of Pro", body: input.detail || "Upgrade to Pro to use it." };
  }
  const copy = LIMIT_COPY[key];
  if (key === "ai_credits_monthly" && typeof input.limit === "number") {
    return { title: copy.limitTitle, body: aiCreditsExhausted(input.limit, context.resetsOn, context.now) };
  }
  if (copy && typeof input.limit === "number") {
    return { title: copy.limitTitle, body: planIncludes(key, input.limit, context.plan) ?? "" };
  }
  return { title: copy?.limitTitle ?? "Plan limit reached", body: input.detail || "Your plan's limit is reached." };
}

/**
 * Some 402s raised before P8 carry only their detail (T4, T5); the dialog still names what they
 * are about. Every 402 from T8.1 carries its entitlement key (C-049), which wins.
 */
export function inferEntitlement(detail: string | null | undefined): string | null {
  if (!detail) return null;
  if (/^Auto mode is part of Pro/i.test(detail)) return "ai_modes";
  if (/AI replies in automations/i.test(detail)) return "ai_reply_automations";
  if (/AI credits/i.test(detail)) return "ai_credits_monthly";
  if (/active automations/i.test(detail)) return "active_automations";
  if (/scheduled posts/i.test(detail)) return "scheduled_posts_monthly";
  if (/characters of knowledge|knowledge limit/i.test(detail)) return "knowledge_characters";
  return null;
}

const CURRENCY_DIGITS = new Map<string, number>();

function currencyDigits(currency: string): number {
  let digits = CURRENCY_DIGITS.get(currency);
  if (digits === undefined) {
    try {
      digits = new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions().maximumFractionDigits ?? 2;
    } catch {
      digits = 2;
    }
    CURRENCY_DIGITS.set(currency, digits);
  }
  return digits;
}

/** A Dodo price in minor units as "₹999" or "$10.50" (§5.1: minor units plus a currency code). */
export function formatPrice(price: { amount_minor: number; currency: string }): string {
  const digits = currencyDigits(price.currency);
  const amount = price.amount_minor / 10 ** digits;
  const whole = Number.isInteger(amount);
  try {
    return new Intl.NumberFormat("en", {
      style: "currency",
      currency: price.currency,
      minimumFractionDigits: whole ? 0 : digits,
      maximumFractionDigits: digits,
    }).format(amount);
  } catch {
    return `${amount} ${price.currency}`;
  }
}

/** "₹999 a month" */
export function pricePerMonth(price: { amount_minor: number; currency: string }): string {
  return `${formatPrice(price)} a month`;
}

export const billingCopy = {
  upgradeCta: "Upgrade to Pro",
  trialCta: (days: number) => `Start ${days}-day trial`,
  trialOffer: (days: number, price: string | null) =>
    price ? `Try Pro free for ${days} days, then ${price}. Cancel anytime.` : `Try Pro free for ${days} days. Cancel anytime.`,
  proPrice: (price: string) => `Pro is ${price}.`,
  ownerOnly: "Only the workspace owner can change the plan.",
  askOwner: "Ask an owner of this workspace to upgrade.",
  confirming: "Confirming your payment…",
  confirmingBody: "This takes a few seconds. Your plan changes as soon as the payment is confirmed.",
  confirmed: (plan: string) => `You're on ${plan}`,
  confirmedTrial: "Your Pro trial has started",
  confirmedBody: "Your new limits are ready to use.",
  slow: "Payment received? It can take a minute. We'll email you when Pro is active.",
  checkoutConflict: "This workspace already has a paid plan. Change it from Manage billing.",
  maxUnavailable: "Max isn't available yet.",
  paymentsUnavailable: "Payments aren't available right now. Try again in a few minutes.",
  noBillingAccount: "There's no billing account for this workspace yet. It's created when you upgrade.",
  cancelled: (plan: string, date: string) => `${plan} until ${date}`,
  resumed: (plan: string) => `${plan} will renew as usual`,
} as const;

/** FR-BIL-06, F-15: the owner's banner while the subscription is on hold. */
export function paymentFailedBanner(graceUntil: string | null): string {
  return graceUntil
    ? `Payment failed. Update your payment method by ${graceUntil} to keep Pro`
    : "Payment failed. Update your payment method to keep Pro";
}

/** The owner's reminder in the last days of a trial (Dodo charges the card when it ends). */
export function trialEndingBanner(daysLeft: number, endsOn: string, renews: boolean, price: string | null): string {
  const when = daysLeft <= 1 ? "tomorrow" : `in ${daysLeft} days`;
  if (!renews) return `Your Pro trial ends ${when}, on ${endsOn}. The workspace moves to Free then`;
  return price
    ? `Your Pro trial ends ${when}, on ${endsOn}. Pro then continues at ${price}`
    : `Your Pro trial ends ${when}, on ${endsOn}. Pro then continues on your card`;
}

// ---- notifications and push (P8: FR-NOT-03, FR-NOT-04, F-19, UX-SCR-07)

export const PUSH_EVENT_COPY = {
  needs_you: { label: "Needs you", hint: "A conversation the AI handed to you." },
  new_lead: { label: "New lead", hint: "Someone looks ready to buy." },
  window_closing: { label: "Reply window closing", hint: "A lead's 24-hour reply window is about to close." },
  account: { label: "Account problems", hint: "An account needs reconnecting or was disconnected." },
} as const;

export const unsubscribeCopy = {
  working: "Unsubscribing…",
  doneTitle: "You're unsubscribed",
  done: (workspace: string) =>
    `You won't get the weekly digest for ${workspace} any more. Turn it back on anytime in Settings → Notifications.`,
  invalidTitle: "This link doesn't work",
  invalid:
    "It may be incomplete, or from a workspace you've left. You can change your emails in Settings → Notifications.",
  missingTitle: "This link is incomplete",
  missing: "Open the unsubscribe link from the email again, or change your emails in Settings → Notifications.",
  failedTitle: "That didn't work",
} as const;
