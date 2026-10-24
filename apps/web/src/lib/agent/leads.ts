/**
 * The lead list and its "Prepare replies" follow-up (VIS-08, VIS-12). The API picks which
 * conversations to draft for (`reply_ids`, a few at a time so the run stays inside its credit and
 * tool-call caps); this words the request and the row labels. Pure, tested directly.
 */
import type { LeadListVisual, LeadRow } from "@/lib/api/types";

const STAGE_LABEL: Record<LeadRow["lead_stage"], string> = {
  new: "New",
  qualified: "Qualified",
  follow_up: "Follow up",
  won: "Won",
  lost: "Lost",
};

export function stageLabel(stage: LeadRow["lead_stage"]): string {
  return STAGE_LABEL[stage];
}

/** "Score 82", or "No score" for a lead that has none yet (never 0). */
export function scoreText(score: number | null | undefined): string {
  return score === null || score === undefined ? "No score" : `Score ${score}`;
}

/** How many more leads wait than the list shows, or 0. */
export function moreLeads(visual: Pick<LeadListVisual, "total" | "items">): number {
  return Math.max(visual.total - visual.items.length, 0);
}

/**
 * The follow-up question for the agent. It carries ids only (no customer text goes into a prompt),
 * asks for one draft_reply per conversation, and says nothing is sent. A closed reply window makes
 * that draft fail on its own, so the request tells the agent to skip it and say so.
 */
export function prepareRepliesRequest(conversationIds: readonly string[]): string {
  return (
    "Prepare replies for these leads. Use draft_reply once for each of these conversations, " +
    `one at a time, and send nothing: ${conversationIds.join(", ")}. ` +
    "If a reply window is closed, skip that conversation and say so."
  );
}

/** The line under the button: what it does and how far it goes. */
export function prepareRepliesHint(count: number): string {
  return `Drafts a reply for the top ${count === 1 ? "lead" : `${count} leads`}. Nothing is sent.`;
}
