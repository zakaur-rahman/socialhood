"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { SourceSheet, type KnowledgeUploader, type SourceSheetMode } from "@/components/knowledge/SourceSheet";
import { keys, useKnowledgeGaps } from "@/lib/api/queries";
import type { Conversation, KnowledgeGap, KnowledgeSource } from "@/lib/api/types";
import { flattenMessages, type MessagePages } from "@/lib/inbox/cache";
import { useCurrentWorkspace } from "@/lib/workspace";

/** The open gap a customer message was counted in (its examples name the message), or null. */
export function gapFor(gaps: KnowledgeGap[] | undefined, messageId: string | null): KnowledgeGap | null {
  if (!gaps || !messageId) return null;
  return gaps.find((gap) => gap.examples.some((example) => example.message_id === messageId)) ?? null;
}

/**
 * The customer's latest message, as Teach AI asks it: the analysed one from the thread's loaded
 * messages, else the list preview when the customer wrote last.
 */
export function latestQuestion(
  conversation: Conversation,
  pages: MessagePages | undefined,
): { messageId: string | null; text: string } {
  const messageId = conversation.latest_analysis?.message_id ?? null;
  const messages = flattenMessages(pages);
  const analysed = messageId ? messages.find((m) => m.id === messageId) : undefined;
  const latest = analysed ?? [...messages].reverse().find((m) => m.direction === "inbound" && m.source === "customer");
  if (latest?.text) return { messageId: latest.id, text: latest.text };
  const preview = conversation.last_message_direction === "inbound" ? (conversation.last_message_preview ?? "") : "";
  return { messageId, text: preview };
}

/**
 * Teach AI (C-063): "Add to knowledge" prefilled with the customer's question as an FAQ, in the
 * existing knowledge source sheet. When the question was counted as a knowledge gap, the FAQ is
 * saved with that gap's id, so answering it resolves the gap (F-17). Owners and admins only: the
 * gaps list and knowledge writes are theirs.
 */
export function useTeachAi({
  upload,
  onSaved,
}: {
  upload?: KnowledgeUploader;
  onSaved?: (source: KnowledgeSource) => void;
} = {}): {
  canTeach: boolean;
  opening: boolean;
  teach: (question: string, messageId: string | null) => Promise<void>;
  sheet: ReactNode;
} {
  const workspace = useCurrentWorkspace();
  const canTeach = workspace.role !== "agent";
  // Read when Teach AI is used, not whenever a conversation opens.
  const gaps = useKnowledgeGaps(workspace.id, false);
  const [mode, setMode] = useState<SourceSheetMode | null>(null);
  const [opening, setOpening] = useState(false);

  const teach = async (question: string, messageId: string | null) => {
    if (!canTeach) return;
    let list = gaps.data?.items;
    if (!list) {
      setOpening(true);
      list = (await gaps.refetch()).data?.items; // a failure only loses the gap link
      setOpening(false);
    }
    const gap = gapFor(list, messageId);
    setMode({ kind: "create", type: "faq", question, ...(gap ? { gapId: gap.id } : {}) });
  };

  const sheet = (
    <SourceSheet
      mode={mode}
      onOpenChange={(open) => (open ? undefined : setMode(null))}
      upload={upload}
      onSaved={onSaved}
    />
  );

  return { canTeach, opening, teach, sheet };
}

/** The thread's cached messages (no request): Teach AI reads the question from them. */
export function useCachedMessages(conversationId: string): () => MessagePages | undefined {
  const queryClient = useQueryClient();
  const workspace = useCurrentWorkspace();
  return () => queryClient.getQueryData<MessagePages>(keys.messages(workspace.id, conversationId));
}
