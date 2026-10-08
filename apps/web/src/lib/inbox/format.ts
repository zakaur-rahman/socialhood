/** Presentation rules for the inbox (UX-INB-04…07). Pure functions, tested directly. */
import type {
  AiMode,
  ContactSummary,
  ConversationListItem,
  EscalationReason,
  MessageKind,
  Platform,
  ReplyWindow,
  Signal,
} from "@/lib/api/types";
import { IDENTITIES, identityFor } from "@/lib/ui/identity";
import type { Tone } from "@/lib/ui/tone";

export const PLATFORM_LABEL: Record<Platform, string> = { instagram: "Instagram", whatsapp: "WhatsApp" };

export function contactName(contact: Pick<ContactSummary, "display_name" | "username">, platform: Platform): string {
  return contact.display_name?.trim() || contact.username || `${PLATFORM_LABEL[platform]} user`;
}

export function firstName(name: string): string {
  return name.replace(/^@/, "").split(/\s+/)[0] || name;
}

/** "You: ", "AI: ", "Auto: " before outbound previews (UX-INB-04). */
export function previewPrefix(item: Pick<ConversationListItem, "last_message_direction" | "last_message_source">): string {
  if (item.last_message_direction !== "outbound") return "";
  switch (item.last_message_source) {
    case "ai_auto":
      return "AI: ";
    case "automation":
      return "Auto: ";
    case "human":
    case "native_app":
      return "You: ";
    default:
      return "";
  }
}

/** Preview labels for messages without text, as the API's ATTACHMENT_PREVIEW. */
export const ATTACHMENT_LABEL: Partial<Record<MessageKind, string>> = {
  image: "Photo",
  video: "Video",
  audio: "Voice message",
  file: "File",
  sticker: "Sticker",
  story_mention: "Mentioned you in a story",
  story_reply: "Story reply",
  share: "Shared a post",
  template: "Template",
  location: "Location",
  unsupported: "Message",
};

export function previewText(item: Pick<ConversationListItem, "last_message_preview" | "last_message_kind">): string {
  if (item.last_message_preview) return item.last_message_preview;
  return (item.last_message_kind && ATTACHMENT_LABEL[item.last_message_kind]) || "";
}

/** Compact time left: "45m", "18h", "5d". */
export function timeLeft(closesAt: string, now: Date): string {
  const minutes = Math.max(0, Math.floor((new Date(closesAt).getTime() - now.getTime()) / 60_000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/** The status tones live in lib/ui/tone (Badge's source); re-exported until the sweeps import it. */
export type { Tone };
export { TONE_CLASS } from "@/lib/ui/tone";

/** FR-INB-01 "Leads" and the Lead badge: the API's inbox_views.LEAD_SCORE. */
export const LEAD_SCORE = 60;

/**
 * `hint`: more about the badge, in a Tooltip on hover (UI-ISS-042). `srDetail`: what screen readers
 * hear after the label, when the hint says something the label doesn't ("Needs you: refund").
 */
export type RowBadge = { key: string; label: string; tone: Tone; hint?: string; srDetail?: string };

/** The AI mode that applies to a conversation: its own, else its account's (FR-SUG-01). */
export function effectiveAiMode(
  item: Pick<ConversationListItem, "ai_mode_override">,
  accountMode: AiMode | null | undefined,
): AiMode | null {
  return item.ai_mode_override ?? accountMode ?? null;
}

/**
 * The row's small badges (UX-INB-04, C-063): "Needs you" when escalated, the other signals
 * (complaint, closing soon, negative), "Lead 72/100" at the lead threshold, and "AI Auto" when
 * the AI replies on its own.
 */
export function rowBadges(
  item: Pick<
    ConversationListItem,
    "needs_human" | "needs_human_reason" | "signal" | "reply_window_closes_at" | "lead_score"
  >,
  now: Date,
  aiMode: AiMode | null,
): RowBadge[] {
  const badges: RowBadge[] = [];
  if (item.needs_human) {
    const reason = item.needs_human_reason ? ESCALATION_LABEL[item.needs_human_reason] : null;
    badges.push({
      key: "needs_you",
      label: "Needs you",
      tone: "danger",
      ...(reason ? { hint: `The AI handed this over: ${reason}`, srDetail: `: ${reason}` } : {}),
    });
  }
  if (item.signal === "complaint" || item.signal === "closing_soon" || item.signal === "negative") {
    const chip = signalChip(item, now);
    if (chip) badges.push({ key: item.signal, ...chip });
  }
  if (item.lead_score !== null && item.lead_score !== undefined && item.lead_score >= LEAD_SCORE) {
    badges.push({ key: "lead", label: `Lead ${item.lead_score}/100`, tone: "brand" });
  }
  if (aiMode === "auto") {
    badges.push({ key: "ai", label: "AI Auto", tone: "success", hint: "The AI replies on its own in this conversation" });
  }
  return badges;
}

/** The one signal chip of a row (UX-INB-04), or null. */
export function signalChip(
  item: Pick<ConversationListItem, "signal" | "reply_window_closes_at">,
  now: Date,
): { label: string; tone: Tone } | null {
  const signal: Signal | null | undefined = item.signal;
  switch (signal) {
    case "needs_you":
      return { label: "Needs you", tone: "danger" };
    case "complaint":
      return { label: "Complaint", tone: "danger" };
    case "closing_soon": {
      const left = item.reply_window_closes_at ? timeLeft(item.reply_window_closes_at, now) : "3h";
      return { label: `Closing in ${left}`, tone: "warning" };
    }
    case "lead":
      return { label: "Lead", tone: "brand" };
    case "negative":
      return { label: "Negative", tone: "danger" };
    default:
      return null;
  }
}

const TWO_HOURS = 2 * 60 * 60 * 1000;

/** The reply window chip in the thread header (UX-INB-05). */
export function windowChip(window: ReplyWindow, now: Date): { label: string; tone: Tone } {
  switch (window.state) {
    case "open": {
      if (!window.closes_at) return { label: "Window open", tone: "neutral" };
      const ms = new Date(window.closes_at).getTime() - now.getTime();
      return { label: `Window: ${timeLeft(window.closes_at, now)} left`, tone: ms < TWO_HOURS ? "warning" : "neutral" };
    }
    case "human_agent":
      return {
        label: window.closes_at ? `Human Agent: ${timeLeft(window.closes_at, now)} left` : "Human Agent",
        tone: "warning",
      };
    case "template_only":
      return { label: "Template only", tone: "warning" };
    case "closed":
    default:
      return { label: "Window closed", tone: "danger" };
  }
}

export const ESCALATION_LABEL: Record<EscalationReason, string> = {
  refund: "refund",
  legal: "legal",
  complaint: "complaint",
  negative_sentiment: "negative sentiment",
  abuse: "abuse",
  account_or_payment: "account or payment",
  human_requested: "asked for a person",
  low_confidence: "low confidence",
  out_of_knowledge: "not in knowledge",
  window_closed: "window closed",
  policy_keyword: "policy keyword",
  output_blocked: "reply blocked",
};

/**
 * The avatar fallback's gradient pairs: the identity palette's (lib/ui/identity, D-13), not status
 * or platform colours; the contact id picks one (UX-INB-04).
 */
export const AVATAR_GRADIENTS: readonly string[] = IDENTITIES.map((identity) => identity.gradient);

export function avatarGradient(id: string): string {
  return identityFor(id).gradient;
}

export function initial(name: string): string {
  const letter = name.replace(/^@/, "").trim().charAt(0);
  return letter ? letter.toUpperCase() : "?";
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Where "Open in Instagram" or "Open in WhatsApp" goes for a contact. */
export function platformContactUrl(
  platform: Platform,
  contact: { username?: string | null; platform_user_id?: string | null },
): string {
  if (platform === "whatsapp") {
    const number = contact.platform_user_id?.replace(/\D/g, "");
    return number ? `https://wa.me/${number}` : "https://web.whatsapp.com/";
  }
  return contact.username ? `https://www.instagram.com/${contact.username}/` : "https://www.instagram.com/direct/inbox/";
}
