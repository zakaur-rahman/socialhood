import type { ActionCard, PreparedCard, ProposalCard } from "@/lib/api/types";

/**
 * GR-36: a proposed write (waits for a member's approval) rather than a prepared action (opens a
 * screen pre-filled). The two are drawn by different components.
 */
export function isProposal(card: ActionCard): card is ProposalCard {
  return card.kind === "flow_proposal" || card.kind === "segment_proposal";
}

export function isPrepared(card: ActionCard): card is PreparedCard {
  return !isProposal(card);
}
