/** Presentation rules for AI state (FR-AI-02, FR-SUG-01…06, UX-INB-08/09). Pure, tested directly. */
import type {
  AiDecisionCheck,
  AiMode,
  BrandTone,
  EmojiPolicy,
  EscalationReason,
  Intent,
  Priority,
  Sentiment,
  SuggestionSource,
  TakeoverMinutes,
} from "@/lib/api/types";
import type { Tone } from "@/lib/inbox/format";

// §5.5 enum values, in the order the correction menu lists them.
export const INTENTS: Intent[] = [
  "pricing",
  "product_inquiry",
  "purchase",
  "order_status",
  "shipping",
  "support",
  "complaint",
  "refund",
  "feedback",
  "collaboration",
  "greeting",
  "spam",
  "other",
];

export const INTENT_LABEL: Record<Intent, string> = {
  pricing: "Pricing",
  product_inquiry: "Product question",
  purchase: "Purchase",
  order_status: "Order status",
  shipping: "Shipping",
  support: "Support",
  complaint: "Complaint",
  refund: "Refund",
  feedback: "Feedback",
  collaboration: "Collaboration",
  greeting: "Greeting",
  spam: "Spam",
  other: "Other",
};

export const SENTIMENTS: Sentiment[] = ["positive", "neutral", "negative"];

export const SENTIMENT_LABEL: Record<Sentiment, string> = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
};

/** The coloured dot beside the sentiment (UX-INB-09). */
export const SENTIMENT_DOT: Record<Sentiment, string> = {
  positive: "bg-success",
  neutral: "bg-fg-secondary",
  negative: "bg-danger",
};

export const PRIORITY_LABEL: Record<Priority, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const PRIORITY_TONE: Record<Priority, Tone> = {
  critical: "danger",
  high: "warning",
  medium: "neutral",
  low: "neutral",
};

// ---- modes (FR-SUG-01)

export const AI_MODES: AiMode[] = ["off", "suggest", "auto"];

export const AI_MODE_LABEL: Record<AiMode, string> = { off: "Off", suggest: "Suggest", auto: "Auto" };

export const AI_MODE_HINT: Record<AiMode, string> = {
  off: "No AI replies",
  suggest: "AI drafts, you send",
  auto: "AI sends when it's confident",
};

/** Built-in escalation rules (FR-SUG-06), for the Auto confirmation and Settings → AI. */
export const BUILT_IN_ESCALATIONS = [
  "The customer asks for a refund",
  "The customer mentions legal action",
  "A complaint with negative sentiment",
  "Abusive messages",
  "The AI isn't confident in its answer",
  "The answer isn't in your knowledge",
] as const;

// ---- takeover (FR-SUG-05)

export const TAKEOVER_OPTIONS: { value: TakeoverMinutes; label: string }[] = [
  { value: 30, label: "30 min" },
  { value: 120, label: "2 h" },
  { value: 1440, label: "24 h" },
  { value: 0, label: "Until resumed" },
];

export function takeoverText(minutes: TakeoverMinutes): string {
  switch (minutes) {
    case 0:
      return "until you resume it";
    case 30:
      return "for 30 minutes";
    case 1440:
      return "for 24 hours";
    case 120:
    default:
      return "for 2 hours";
  }
}

// ---- brand voice (FR-KB-04)

export const TONE_OPTIONS: { value: BrandTone; label: string }[] = [
  { value: "friendly", label: "Friendly" },
  { value: "professional", label: "Professional" },
  { value: "playful", label: "Playful" },
  { value: "concise", label: "Concise" },
];

export const EMOJI_OPTIONS: { value: EmojiPolicy; label: string }[] = [
  { value: "none", label: "None" },
  { value: "light", label: "Light" },
  { value: "lots", label: "Lots" },
];

// ---- escalations and decisions (F-09, TR-AI-07)

/** "AI didn't reply: {reason}" (UX-INB-08). */
export const ESCALATION_SENTENCE: Record<EscalationReason, string> = {
  refund: "customer is asking for a refund",
  legal: "customer mentioned legal action",
  complaint: "customer is complaining",
  negative_sentiment: "customer sounds upset",
  abuse: "the message is abusive",
  account_or_payment: "it's about an account or payment problem",
  human_requested: "customer asked for a person",
  low_confidence: "it wasn't confident in its answer",
  out_of_knowledge: "the answer isn't in your knowledge",
  window_closed: "the reply window is closed",
  policy_keyword: "the message has one of your escalation phrases",
  output_blocked: "its reply had a link or number that isn't in your knowledge",
};

export function escalationBanner(reason: EscalationReason): string {
  return `AI didn't reply: ${ESCALATION_SENTENCE[reason]}`;
}

/** TR-AI-07's checks by number; an unknown check shows the API's name. */
const CHECK_LABEL: Record<number, string> = {
  1: "AI mode is Auto",
  2: "Plan and AI credits allow it",
  3: "AI isn't paused",
  4: "No automation answered",
  5: "Reply window is open",
  6: "No person needed",
  7: "No refund, complaint or escalation phrase",
  8: "Customer isn't upset",
  9: "Answer is in your knowledge",
  10: "AI is confident",
  11: "Answer is backed by your knowledge",
  12: "Under the AI reply limit",
  13: "Links and numbers come from your knowledge",
};

export function checkLabel(check: AiDecisionCheck): string {
  return CHECK_LABEL[check.n] ?? check.name.replaceAll("_", " ");
}

/** Confidence and similarity as a percentage; other values as given. */
export function checkValue(check: AiDecisionCheck): string | null {
  const value = check.value;
  if (value === null || value === undefined || typeof value === "boolean") return null;
  if (typeof value === "number") return value >= 0 && value <= 1 ? `${Math.round(value * 100)}%` : String(value);
  return value;
}

// ---- suggestions (UX-INB-08)

/** "From: Shipping policy", at most two, then "+n". */
export function sourceChips(sources: SuggestionSource[]): { shown: SuggestionSource[]; more: number } {
  return { shown: sources.slice(0, 2), more: Math.max(0, sources.length - 2) };
}
