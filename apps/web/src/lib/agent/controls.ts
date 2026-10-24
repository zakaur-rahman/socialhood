/**
 * Range and platform controls on a visual (VIS-11). A control never queries data: changing one
 * asks the same question again in the thread as a structured follow-up (`hints` on the run), so the
 * agent's rules, role checks and credits apply as for any question. Pure, tested directly.
 */
import { aiCreditsExhausted } from "@/lib/copy";
import type { RunHints, Visual } from "@/lib/api/types";

export const RANGE_OPTIONS = [7, 30, 90] as const;
export type RangeDays = (typeof RANGE_OPTIONS)[number];

export const PLATFORM_OPTIONS = [
  { value: "all", label: "All platforms" },
  { value: "instagram", label: "Instagram" },
  { value: "facebook", label: "Facebook" },
  { value: "whatsapp", label: "WhatsApp" },
] as const;
export type PlatformChoice = (typeof PLATFORM_OPTIONS)[number]["value"];

/**
 * What one change costs: a run's model calls, 1 credit each (billing/plans.CREDIT_COSTS
 * "agent_turn"), and a typical question takes 2 to 4. The same run, so the same price as asking.
 */
export const CONTROL_CREDITS = { min: 2, max: 4 } as const;

export const costWords = `About ${CONTROL_CREDITS.min} to ${CONTROL_CREDITS.max} AI credits`;

export type Selection = { rangeDays: RangeDays | null; platform: PlatformChoice | null };

/** The visuals that offer controls; a table or a lead list has no range or platform to change. */
export function offersControls(visual: Visual): boolean {
  switch (visual.kind) {
    case "trend":
      return true;
    case "metric_comparison":
      return true;
    case "ranked_posts":
    case "sentiment_summary":
      return Boolean(visual.period); // a single post has no range to change
    default:
      return false;
  }
}

function periodDays(visual: Visual): number | null {
  switch (visual.kind) {
    case "trend":
      return visual.period.days;
    case "metric_comparison":
      return visual.current.days;
    case "ranked_posts":
    case "sentiment_summary":
      return visual.period?.days ?? null;
    default:
      return null;
  }
}

/**
 * What the visual is showing now: the range from its own period when it is one of the offered
 * ones, the platform from the follow-up that made it (a question typed in words names none).
 */
export function currentSelection(visual: Visual, hints: RunHints | null | undefined): Selection {
  const days = hints?.range_days ?? periodDays(visual);
  const rangeDays = RANGE_OPTIONS.find((option) => option === days) ?? null;
  const platform = PLATFORM_OPTIONS.find((option) => option.value === hints?.platform)?.value ?? null;
  return { rangeDays, platform };
}

/** The follow-up for a change: the whole selection, so one control keeps the other's choice. */
export function controlHints(current: Selection, change: Partial<Selection>): RunHints {
  const next = { ...current, ...change };
  return {
    ...(next.rangeDays !== null ? { range_days: next.rangeDays } : {}),
    ...(next.platform !== null ? { platform: next.platform } : {}),
  };
}

export type CreditsNow = { limit: number | null | undefined; used: number; resetsOn?: string | null } | null;

export type ControlGate = { ok: true } | { ok: false; reason: string };

/**
 * Whether a change can run, with the reason when it can't, so the control explains instead of
 * failing. A change needs room for a whole run (the upper estimate); a plan with no credits, or
 * none left, says so with the reset date.
 */
export function controlGate(credits: CreditsNow, now?: Date): ControlGate {
  if (credits === null || credits.limit === null || credits.limit === undefined) return { ok: true };
  if (credits.limit <= 0) {
    return { ok: false, reason: "Your plan has no AI credits, so a change can't ask again. Upgrade to use them." };
  }
  const left = credits.limit - credits.used;
  if (left <= 0) return { ok: false, reason: aiCreditsExhausted(credits.limit, credits.resetsOn, now) };
  if (left < CONTROL_CREDITS.max) {
    const noun = left === 1 ? "AI credit" : "AI credits";
    return {
      ok: false,
      reason: `You have ${left} ${noun} left this month, and a change can use up to ${CONTROL_CREDITS.max}.`,
    };
  }
  return { ok: true };
}
