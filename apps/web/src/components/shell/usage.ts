import { usageMeter } from "@/lib/api/queries/billing";
import type { BillingState, Plan, Role } from "@/lib/api/types";

/** The AI credits meter as the shell reads it: loading, a limited meter, or nothing to show. */
export type CreditsUsage = "loading" | { used: number; limit: number; plan: Plan } | null;

/** From the billing query (the same data as the AI credits banner). No limit means unlimited. */
export function creditsUsage(billing: BillingState | undefined, pending: boolean): CreditsUsage {
  if (pending) return "loading";
  const meter = usageMeter(billing, "ai_credits");
  if (!billing || !meter || meter.limit === null || meter.limit === undefined || meter.limit <= 0) return null;
  return { used: meter.used, limit: meter.limit, plan: billing.plan };
}

export type UsageTone = "normal" | "warning" | "danger";

export type UsageView =
  | { kind: "hidden" }
  | { kind: "loading" }
  | { kind: "meter"; used: number; limit: number; percent: number; tone: UsageTone; upgrade: boolean };

/** Warning-toned from this share of the credits, danger-toned once they are used up. */
export const USAGE_WARNING = 0.8;

/**
 * The sidebar's usage card. Agents never see it; an unlimited plan has nothing to show. Upgrade is
 * offered to owners and admins on Free, or from 80 % of the credits (never on Max, the top plan):
 * a paying customer under 80 % sees only the meter.
 */
export function usageView(usage: CreditsUsage | undefined, role: Role): UsageView {
  if (role === "agent" || !usage) return { kind: "hidden" };
  if (usage === "loading") return { kind: "loading" };
  const ratio = usage.used / usage.limit;
  const tone: UsageTone = ratio >= 1 ? "danger" : ratio >= USAGE_WARNING ? "warning" : "normal";
  // Rounded down, so 99.6 % is not shown as 100 % while credits remain.
  const percent = Math.min(100, Math.max(0, Math.floor(ratio * 100)));
  const upgrade = usage.plan !== "max" && (usage.plan === "free" || ratio >= USAGE_WARNING);
  return { kind: "meter", used: usage.used, limit: usage.limit, percent, tone, upgrade };
}

const count = new Intl.NumberFormat("en-US");

/** "412 of 500 used" */
export function creditsUsedText(used: number, limit: number): string {
  return `${count.format(used)} of ${count.format(limit)} used`;
}
