"use client";

import { create } from "zustand";

import type { ActionCard, AutomationDraftPrefill, CommentReplyPrefill } from "@/lib/api/types";
import { useInboxStore } from "@/lib/inbox/store";
import { uuid } from "@/lib/uuid";

/** Each hand-off is new, even with the same values, so a screen already open takes it again. */
type Fresh = { nonce: string };

export type ScheduleHandoff = Fresh & { sendAt: string | null };
export type CommentReplyHandoff = Fresh & CommentReplyPrefill;
export type AutomationDraftHandoff = Fresh & AutomationDraftPrefill;

type HandoffState = {
  /** A prepared scheduled message, by conversation id: the popover opens at this time. */
  schedule: Record<string, ScheduleHandoff>;
  commentReply: CommentReplyHandoff | null;
  automationDraft: AutomationDraftHandoff | null;
  takeSchedule: (conversationId: string) => void;
  takeCommentReply: (nonce: string) => void;
  takeAutomationDraft: (nonce: string) => void;
};

/**
 * FR-AGT-03: an action card hands its prefilled values to the screen it opens. The screen takes
 * them once (and clears them), shows them in its usual controls, and the member completes the
 * action there, so every existing check applies. Nothing is sent or saved by the hand-off.
 */
export const useAgentHandoff = create<HandoffState>()((set) => ({
  schedule: {},
  commentReply: null,
  automationDraft: null,
  takeSchedule: (conversationId) =>
    set((state) => {
      if (!state.schedule[conversationId]) return state;
      const schedule = { ...state.schedule };
      delete schedule[conversationId];
      return { schedule };
    }),
  takeCommentReply: (nonce) => set((state) => (state.commentReply?.nonce === nonce ? { commentReply: null } : state)),
  takeAutomationDraft: (nonce) =>
    set((state) => (state.automationDraft?.nonce === nonce ? { automationDraft: null } : state)),
}));

/** Puts a card's prefill where its screen looks for it; the caller then opens the card's route. */
export function handOff(card: ActionCard): void {
  const nonce = uuid();
  switch (card.kind) {
    case "schedule_message": {
      const { conversation_id: conversationId, text, send_at: sendAt } = card.prefill;
      // The message goes in the conversation's composer, which the schedule popover sends from.
      useInboxStore.getState().setDraft(conversationId, text);
      useAgentHandoff.setState((state) => ({
        schedule: { ...state.schedule, [conversationId]: { nonce, sendAt: sendAt ?? null } },
      }));
      return;
    }
    case "reply_to_comment":
      useAgentHandoff.setState({ commentReply: { ...card.prefill, nonce } });
      return;
    case "automation_draft":
      useAgentHandoff.setState({ automationDraft: { ...card.prefill, nonce } });
      return;
  }
}

export function resetAgentHandoff(): void {
  useAgentHandoff.setState({ schedule: {}, commentReply: null, automationDraft: null });
}
