import type { BroadcastStatus, RecipientStatus, VariableSpec } from "@/lib/api/types";
import type { Tone } from "@/lib/ui/tone";

/** A broadcast's status in words and tone (GR-23). Colour never stands alone: the badge says it. */
export const BROADCAST_STATUS: Record<BroadcastStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  scheduled: { label: "Scheduled", tone: "brand" },
  sending: { label: "Sending", tone: "brand" },
  paused: { label: "Paused", tone: "warning" },
  completed: { label: "Done", tone: "success" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  failed: { label: "Didn't start", tone: "danger" },
};

export const RECIPIENT_STATUS: Record<RecipientStatus, { label: string; tone: Tone }> = {
  queued: { label: "Waiting", tone: "neutral" },
  sent: { label: "Sent", tone: "brand" },
  delivered: { label: "Delivered", tone: "success" },
  read: { label: "Read", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  skipped: { label: "Skipped", tone: "warning" },
};

export const RECIPIENT_FILTERS: { value: RecipientStatus | null; label: string }[] = [
  { value: null, label: "Everyone" },
  { value: "queued", label: "Waiting" },
  { value: "sent", label: "Sent" },
  { value: "delivered", label: "Delivered" },
  { value: "read", label: "Read" },
  { value: "failed", label: "Failed" },
  { value: "skipped", label: "Skipped" },
];

/** What a template variable can be mapped to besides a workspace's own contact fields. */
export const BUILT_IN_FIELDS: { value: string; label: string }[] = [
  { value: "first_name", label: "First name" },
  { value: "name", label: "Full name" },
  { value: "username", label: "Username" },
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
];

const count = new Intl.NumberFormat("en-IN");

export function formatCount(n: number): string {
  return count.format(n);
}

/** Money as the API sends it (a decimal string) in the currency's own format. */
export function formatMoney(amount: string | number, currency: string): string {
  const value = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(value)) return String(amount);
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
}

/** "42%" of a whole; "0%" when there is no whole. */
export function percent(part: number, whole: number): string {
  if (whole <= 0) return "0%";
  return `${Math.round((part / whole) * 100)}%`;
}

/** The template's body with {{1}}, {{2}}... replaced; a missing one stays as it is. */
export function fillTemplate(body: string, params: string[]): string {
  return body.replace(/\{\{\s*(\d+)\s*\}\}/g, (whole, n: string) => params[Number(n) - 1] ?? whole);
}

/** How a variable is mapped, in a sentence: "First name (or "there")", "31 October". */
export function describeVariable(spec: Pick<VariableSpec, "source" | "field" | "value" | "fallback">, labels: Record<string, string> = {}): string {
  if (spec.source === "fixed") return spec.value ?? "";
  const name = labels[spec.field ?? ""] ?? BUILT_IN_FIELDS.find((f) => f.value === spec.field)?.label ?? spec.field ?? "";
  return spec.fallback ? `${name} (or "${spec.fallback}")` : name;
}

/** Everyone counted as sent has reached WhatsApp at least; delivered and read are further on. */
export function reached(counts: { sent: number; delivered: number; read: number }): number {
  return counts.sent + counts.delivered + counts.read;
}
