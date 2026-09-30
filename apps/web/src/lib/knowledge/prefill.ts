/**
 * "Add to knowledge" prefilled with a customer's question (Home's Train AI, C-065). The value is
 * a create mode of components/knowledge/SourceSheet (structurally its `SourceSheetMode`): an FAQ
 * with the question filled in and, when it answers a knowledge gap, the gap's id, so saving goes
 * through POST …/knowledge-sources with `gap_id` and resolves the gap (F-17). The inbox's Teach AI
 * hand-off can build the same value, so the two can share this later.
 */

export type KnowledgePrefill = {
  kind: "create";
  type: "faq";
  question: string;
  gapId?: string;
};

/** An FAQ for `question`; with `gapId`, saving it answers that gap. */
export function faqPrefill(question: string, gapId?: string | null): KnowledgePrefill {
  const trimmed = question.trim();
  return gapId ? { kind: "create", type: "faq", question: trimmed, gapId } : { kind: "create", type: "faq", question: trimmed };
}

/** Train AI on a gap: its customer's question (the topic when there is no message). */
export function gapPrefill(gap: { id: string; question: string; topic: string }): KnowledgePrefill {
  return faqPrefill(gap.question.trim() || gap.topic, gap.id);
}
