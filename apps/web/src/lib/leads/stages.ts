import type { LeadStage } from "@/lib/api/types";
import type { Tone } from "@/lib/ui/tone";

/** The lead stages (GR-18), in pipeline order. New, qualified and follow up are open. */
export const LEAD_STAGES: readonly { value: LeadStage; label: string; hint: string; tone: Tone }[] = [
  { value: "new", label: "New", hint: "Not sorted yet", tone: "neutral" },
  { value: "qualified", label: "Qualified", hint: "Worth a conversation", tone: "brand" },
  { value: "follow_up", label: "Follow up", hint: "Waiting on you or them", tone: "warning" },
  { value: "won", label: "Won", hint: "Became a customer", tone: "success" },
  { value: "lost", label: "Lost", hint: "Not going ahead", tone: "neutral" },
];

export const STAGE_LABEL: Record<LeadStage, string> = {
  new: "New",
  qualified: "Qualified",
  follow_up: "Follow up",
  won: "Won",
  lost: "Lost",
};

export const STAGE_TONE: Record<LeadStage, Tone> = {
  new: "neutral",
  qualified: "brand",
  follow_up: "warning",
  won: "success",
  lost: "neutral",
};

/** Days without a customer message before a lead goes cold: the choices offered to admins. */
export const COLD_DAY_CHOICES = [3, 5, 7, 14, 30, 60] as const;

/** The choices, plus the current value when an API client set one that is not on the list. */
export function coldDayOptions(current: number): number[] {
  const all: number[] = [...COLD_DAY_CHOICES];
  return all.includes(current) ? all : [...all, current].sort((a, b) => a - b);
}
