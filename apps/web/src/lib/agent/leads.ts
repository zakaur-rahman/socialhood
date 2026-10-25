/**
 * The lead list and its "Prepare replies" follow-up (VIS-08, VIS-12). The API picks which
 * conversations to draft for (`reply_ids`, a few at a time so the run stays inside its credit and
 * tool-call caps); this words the request and the row labels. Pure, tested directly.
 */
import type { LeadListVisual, LeadRow, RunHints } from "@/lib/api/types";

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
 * The follow-up for the agent (VIS-12, VIS-11): a structured hint with ids only. The API words
 * the member's question ("Prepare replies for these leads", no ids in view) and the agent's
 * instruction (one draft_reply per conversation, nothing sent, a closed reply window skipped and
 * said so), so no customer text and no prompt wording comes from the browser.
 */
export function prepareRepliesHints(conversationIds: readonly string[]): RunHints {
  return { reply_conversation_ids: [...conversationIds] };
}

/** The line under the button: what it does and how far it goes. */
export function prepareRepliesHint(count: number): string {
  return `Drafts a reply for the top ${count === 1 ? "lead" : `${count} leads`}. Nothing is sent.`;
}
