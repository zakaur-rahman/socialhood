"use client";

import { create } from "zustand";

import type { Message, SendMessage } from "@/lib/api/types";

/** A reply that has not reached the server's message list yet (TR-FE-05). */
export type OutboxEntry = {
  clientId: string;
  conversationId: string;
  /** The exact body posted, so Retry resends it with the same Idempotency-Key. */
  body: SendMessage;
  /** The optimistic bubble: status queued, or failed with the reason. */
  message: Message;
};

type InboxState = {
  /** Drafts per conversation id, for the session (FR-INB-06, TR-FE-06). */
  drafts: Record<string, string>;
  outbox: Record<string, OutboxEntry>;
  /** The suggestion whose text is being edited in the composer, per conversation (F-08 Edit). */
  suggestionEdits: Record<string, string>;
  setDraft: (conversationId: string, text: string) => void;
  setSuggestionEdit: (conversationId: string, suggestionId: string | null) => void;
  putOutbox: (entry: OutboxEntry) => void;
  patchOutbox: (clientId: string, patch: Partial<Message>) => void;
  removeOutbox: (clientId: string) => void;
};

/**
 * Conversation-specific client state lives here, keyed by conversation id, never in component
 * state that could survive a conversation switch (TR-FE-06).
 */
export const useInboxStore = create<InboxState>()((set) => ({
  drafts: {},
  outbox: {},
  suggestionEdits: {},
  setSuggestionEdit: (conversationId, suggestionId) =>
    set((state) => {
      const suggestionEdits = { ...state.suggestionEdits };
      if (suggestionId) suggestionEdits[conversationId] = suggestionId;
      else delete suggestionEdits[conversationId];
      return { suggestionEdits };
    }),
  setDraft: (conversationId, text) =>
    set((state) => {
      const drafts = { ...state.drafts };
      if (text) drafts[conversationId] = text;
      else delete drafts[conversationId];
      return { drafts };
    }),
  putOutbox: (entry) => set((state) => ({ outbox: { ...state.outbox, [entry.clientId]: entry } })),
  patchOutbox: (clientId, patch) =>
    set((state) => {
      const entry = state.outbox[clientId];
      if (!entry) return state;
      return { outbox: { ...state.outbox, [clientId]: { ...entry, message: { ...entry.message, ...patch } } } };
    }),
  removeOutbox: (clientId) =>
    set((state) => {
      if (!state.outbox[clientId]) return state;
      const outbox = { ...state.outbox };
      delete outbox[clientId];
      return { outbox };
    }),
}));

export function resetInboxStore(): void {
  useInboxStore.setState({ drafts: {}, outbox: {}, suggestionEdits: {} });
}
