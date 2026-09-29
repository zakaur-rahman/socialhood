"use client";

import { create } from "zustand";

type AskState = {
  /** The Ask Social Hood panel (FR-AGT-01). */
  open: boolean;
  /**
   * The thread the panel and the Ask page show, per workspace. null starts a new thread with the
   * next question; the API names it after that run.
   */
  threads: Record<string, string | null>;
  /** What the member is typing, per workspace, so closing the panel keeps it. */
  drafts: Record<string, string>;
  setOpen: (open: boolean) => void;
  setThread: (wid: string, threadId: string | null) => void;
  setDraft: (wid: string, text: string) => void;
};

/** Client state of Ask Social Hood, shared by the panel and the /ask page. */
export const useAskStore = create<AskState>()((set) => ({
  open: false,
  threads: {},
  drafts: {},
  setOpen: (open) => set({ open }),
  setThread: (wid, threadId) => set((state) => ({ threads: { ...state.threads, [wid]: threadId } })),
  setDraft: (wid, text) =>
    set((state) => {
      const drafts = { ...state.drafts };
      if (text) drafts[wid] = text;
      else delete drafts[wid];
      return { drafts };
    }),
}));

export function resetAskStore(): void {
  useAskStore.setState({ open: false, threads: {}, drafts: {} });
}
