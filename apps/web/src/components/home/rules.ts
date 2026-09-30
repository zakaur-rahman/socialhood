/**
 * Home's rule-based labels (C-065). Each follows from the API's numbers, never a model's guess:
 *
 * - **Attention** on Needs reply: at least one conversation needs a reply and the longest-waiting
 *   one has waited more than an hour (`oldest_waiting_since`: when its unanswered turn began).
 * - **Fast** on Median first response: the median is under 5 minutes.
 * - A priority queue row: "Needs you" when the AI handed the conversation to a person; otherwise
 *   "AI draft ready" when a suggested reply waits for review, else "Needs reply". The action is
 *   Review & Send with a draft, Open chat without; both open the conversation in the inbox, where
 *   the draft shows.
 */
import type { PriorityConversation } from "@/lib/api/types";
import type { Tone } from "@/lib/inbox/format";

export const ATTENTION_AFTER_MS = 60 * 60 * 1000;
export const FAST_UNDER_S = 5 * 60;

export function needsAttention(needsReply: number, oldestWaitingSince: string | null, now: Date): boolean {
  if (needsReply <= 0 || oldestWaitingSince === null) return false;
  return now.getTime() - new Date(oldestWaitingSince).getTime() > ATTENTION_AFTER_MS;
}

export function isFast(medianSeconds: number | null | undefined): boolean {
  return medianSeconds !== null && medianSeconds !== undefined && medianSeconds < FAST_UNDER_S;
}

export type QueueState = {
  chip: { label: string; tone: Tone };
  action: "Review & Send" | "Open chat";
};

export function queueState(item: Pick<PriorityConversation, "needs_you" | "has_pending_suggestion">): QueueState {
  const action = item.has_pending_suggestion ? "Review & Send" : "Open chat";
  if (item.needs_you) return { chip: { label: "Needs you", tone: "danger" }, action };
  if (item.has_pending_suggestion) return { chip: { label: "AI draft ready", tone: "brand" }, action };
  return { chip: { label: "Needs reply", tone: "warning" }, action };
}
