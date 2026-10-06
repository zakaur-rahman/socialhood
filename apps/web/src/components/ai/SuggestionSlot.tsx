"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import type { KnowledgeUploader } from "@/components/knowledge/SourceSheet";
import { TOAST_ACTION_DURATION } from "@/components/ui/sonner";
import {
  exhaustedAiCredits,
  useBilling,
  useDismissSuggestion,
  useRegenerateSuggestion,
  type ReplyInput,
} from "@/lib/api/queries";
import type { Conversation, Message, Suggestion } from "@/lib/api/types";
import { escalationBanner } from "@/lib/ai/format";
import { toastError } from "@/lib/toast-error";
import { setPendingSuggestion } from "@/lib/inbox/cache";
import { contactName, firstName } from "@/lib/inbox/format";
import { useInboxStore } from "@/lib/inbox/store";
import { useCurrentWorkspace } from "@/lib/workspace";

import { EditingSuggestionChip, EscalationBanner, SuggestionCard } from "./SuggestionCard";
import { useTeachAi } from "./TeachAi";

/** How long after an analysis the first draft is awaited (TR-AI-06: ready within 12 s p95). */
export const DRAFT_WAIT_MS = 30_000;
/** How long a regenerated draft is awaited before the card says it didn't come. */
export const REGENERATE_WAIT_MS = 30_000;

/** True until `ms` after `since`; re-renders when it flips. */
function useWithin(since: string | null, ms: number): boolean {
  const deadline = since ? new Date(since).getTime() + ms : 0;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!deadline) return;
    const timer = window.setTimeout(() => setNow(Date.now()), Math.max(0, deadline - Date.now()) + 10);
    return () => window.clearTimeout(timer);
  }, [deadline]);
  return deadline > now;
}

export function composerId(conversationId: string): string {
  return `composer-${conversationId}`;
}

export function focusComposer(conversationId: string): void {
  const el = document.getElementById(composerId(conversationId));
  if (el instanceof HTMLTextAreaElement) {
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }
}

export type SuggestionKeys = { send: () => void; dismiss: () => void } | null;

/**
 * F-08 above the composer: the escalation banner (Auto), then the suggestion card in its state,
 * or the "Editing suggestion" chip. Send posts the text with suggestion_id; Edit moves it into
 * the composer; Regenerate shimmers until suggestion.created; Dismiss closes it.
 */
export function useSuggestionSlot({
  conversation,
  messages,
  canReply,
  onSend,
  upload,
}: {
  conversation: Conversation;
  /** Loaded messages, oldest first: the question a suggestion answers. */
  messages: Message[];
  /** The composer can send (window open, account connected). */
  canReply: boolean;
  onSend: (input: ReplyInput) => void;
  upload?: KnowledgeUploader;
}) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const conversationId = conversation.id;
  const queryClient = useQueryClient();
  const regenerate = useRegenerateSuggestion(wid, conversationId);
  const dismiss = useDismissSuggestion(wid, conversationId);
  const billing = useBilling(wid);
  const editingId = useInboxStore((state) => state.suggestionEdits[conversationId] ?? null);
  const setSuggestionEdit = useInboxStore((state) => state.setSuggestionEdit);
  const setDraft = useInboxStore((state) => state.setDraft);
  const [waitingFor, setWaitingFor] = useState<string | null>(null);

  const suggestion: Suggestion | null = conversation.pending_suggestion ?? null;
  const name = firstName(contactName(conversation.contact, conversation.platform));
  const humanAgent = conversation.reply_window.state === "human_agent";
  const aiOn = conversation.ai.effective_mode !== "off";
  const outOfCredits = Boolean(exhaustedAiCredits(billing.data));

  // Regenerating: the card shimmers until a different suggestion replaces this one.
  const regenerating = waitingFor !== null && (suggestion?.id ?? null) === waitingFor;
  const currentId = useRef(suggestion?.id ?? null);
  useEffect(() => {
    currentId.current = suggestion?.id ?? null;
  });
  useEffect(() => {
    if (!waitingFor) return;
    const timer = window.setTimeout(() => {
      if (currentId.current === waitingFor) toast.error("No new draft arrived. Try again.");
      setWaitingFor(null);
    }, REGENERATE_WAIT_MS);
    return () => window.clearTimeout(timer);
  }, [waitingFor]);

  // The first draft: the latest customer message was just analysed as needing a reply, and
  // nobody has answered it yet (a sent or dismissed draft, or a reply of their own, closes the
  // card rather than bringing the shimmer back).
  const [handledFor, setHandledFor] = useState<string | null>(null);
  const analysis = conversation.latest_analysis ?? null;
  const lastInbound = [...messages].reverse().find((m) => m.direction === "inbound") ?? null;
  const answered =
    lastInbound !== null && messages.slice(messages.indexOf(lastInbound) + 1).some((m) => m.direction === "outbound");
  const fresh = useWithin(analysis?.created_at ?? null, DRAFT_WAIT_MS);
  const drafting =
    !suggestion &&
    aiOn &&
    !outOfCredits &&
    fresh &&
    Boolean(analysis?.needs_reply) &&
    lastInbound !== null &&
    analysis?.message_id === lastInbound.id &&
    handledFor !== lastInbound.id &&
    !answered;

  // A superseded suggestion can't be sent: the text stays, the link goes.
  useEffect(() => {
    if (editingId && suggestion?.id !== editingId) setSuggestionEdit(conversationId, null);
  }, [editingId, suggestion?.id, conversationId, setSuggestionEdit]);

  const question =
    (suggestion && messages.find((m) => m.id === suggestion.message_id)?.text) || lastInbound?.text || "";

  const send = () => {
    if (!suggestion?.reply_text || !canReply) return;
    onSend({ text: suggestion.reply_text, suggestionId: suggestion.id, humanAgent });
    setHandledFor(suggestion.message_id);
    setPendingSuggestion(queryClient, wid, conversationId, null, suggestion.id);
    setSuggestionEdit(conversationId, null);
  };

  const close = () => {
    if (!suggestion) return;
    setHandledFor(suggestion.message_id);
    setSuggestionEdit(conversationId, null);
    dismiss.mutate(suggestion, { onError: (error) => toastError(error) });
  };

  const redraft = () => {
    if (!suggestion) return;
    setWaitingFor(suggestion.id);
    regenerate.mutate(undefined, {
      onError: (error) => {
        setWaitingFor(null);
        toastError(error); // out of credits (402): the upgrade dialog says so
      },
    });
  };

  const edit = () => {
    if (!suggestion?.reply_text) return;
    setDraft(conversationId, suggestion.reply_text);
    setSuggestionEdit(conversationId, suggestion.id);
    requestAnimationFrame(() => focusComposer(conversationId));
  };

  // Add to knowledge is Teach AI (C-063): the FAQ answers the question's gap, when it was counted.
  const teachAi = useTeachAi({
    upload,
    onSaved: () => {
      if (suggestion && suggestion.regenerations_left > 0) {
        toast("The AI can use it once it's processed.", {
          action: { label: "Draft again", onClick: redraft },
          duration: TOAST_ACTION_DURATION,
        });
      }
    },
  });

  const escalation =
    conversation.needs_human && conversation.needs_human_reason && conversation.ai.effective_mode === "auto"
      ? escalationBanner(conversation.needs_human_reason)
      : null;

  const showCard = canReply && (suggestion !== null || drafting || regenerating);
  const editing = Boolean(editingId && suggestion?.id === editingId);

  const slot = (
    <>
      {escalation ? <EscalationBanner message={escalation} /> : null}
      {showCard ? (
        editing ? (
          <EditingSuggestionChip onStop={() => setSuggestionEdit(conversationId, null)} />
        ) : (
          <SuggestionCard
            suggestion={suggestion}
            generating={regenerating || (!suggestion && drafting)}
            customerName={name}
            canSend={canReply}
            busy={dismiss.isPending || regenerate.isPending}
            addingToKnowledge={teachAi.opening}
            actions={{
              onSend: send,
              onEdit: edit,
              onRegenerate: redraft,
              onDismiss: close,
              onWriteReply: () => focusComposer(conversationId),
              onAddToKnowledge: teachAi.canTeach
                ? () => void teachAi.teach(question, suggestion?.message_id ?? lastInbound?.id ?? null)
                : undefined,
            }}
          />
        )
      ) : null}
      {teachAi.sheet}
    </>
  );

  // Ctrl/⌘ Enter sends and Esc dismisses, from an empty composer (UX-INB-08).
  const keys: SuggestionKeys =
    showCard && !editing && suggestion && !regenerating
      ? { send: suggestion.can_answer ? send : () => {}, dismiss: close }
      : null;

  return { slot, keys };
}
