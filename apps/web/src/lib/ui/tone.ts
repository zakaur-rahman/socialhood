/**
 * The status tones, in one place (DESIGN_SYSTEM §1.5, §8.2; UI-ISS-027). Badge reads this map,
 * and the inbox's `TONE_CLASS` and the schedule's `CHIP_CLASS` are this map re-exported, so
 * every status chip shows the same fill and text for a tone.
 *
 * - `neutral`: the `hover` fill (white 5%) with secondary text. Not `pressed`: secondary text is
 *   only 4.45:1 on it.
 * - `brand`: the info tone, `brand-soft` with `brand-fg` text.
 * - `success`, `warning`, `danger`: the 15% soft fills with the status text colour (`danger-fg`,
 *   since `danger` is never text).
 */
export type Tone = "neutral" | "brand" | "success" | "warning" | "danger";

export const TONES: readonly Tone[] = ["neutral", "brand", "success", "warning", "danger"];

export const TONE_CLASS: Record<Tone, string> = {
  neutral: "bg-hover text-fg-secondary",
  brand: "bg-brand-soft text-brand-fg",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger-fg",
};
