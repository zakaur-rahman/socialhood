"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import { HashtagGroupsDialog } from "@/components/schedule/HashtagGroupsDialog";
import { PostingTimesDrawer } from "@/components/schedule/PostingTimesDrawer";
import type { SocialAccount } from "@/lib/api/types";

type Tool = "times" | "hashtags";

type ComposerToolsValue = {
  /** Opens Posting times in place. `from` gets focus back when it closes. */
  openPostingTimes: (from?: HTMLElement | null) => void;
  /** Opens Hashtag groups in place. `from` gets focus back when it closes. */
  openHashtagGroups: (from?: HTMLElement | null) => void;
};

const ComposerToolsContext = createContext<ComposerToolsValue | null>(null);

/** The tools the composer used to send you to /schedule for; null outside the composer. */
export function useComposerTools(): ComposerToolsValue | null {
  return useContext(ComposerToolsContext);
}

/**
 * UI-054: Posting times (a side sheet) and Hashtag groups (a dialog) open over the composer, so
 * the draft stays where it is. The control that asked gets focus back on close.
 */
export function ComposerTools({
  wid,
  timeZone,
  now,
  accounts,
  children,
}: {
  wid: string;
  timeZone: string;
  now: Date;
  accounts: SocialAccount[];
  children: ReactNode;
}) {
  const [open, setOpen] = useState<Tool | null>(null);
  const from = useRef<HTMLElement | null>(null);
  const show = useCallback((tool: Tool, element?: HTMLElement | null) => {
    from.current = element ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    setOpen(tool);
  }, []);
  const value = useMemo<ComposerToolsValue>(
    () => ({
      openPostingTimes: (element) => show("times", element),
      openHashtagGroups: (element) => show("hashtags", element),
    }),
    [show],
  );
  const returnFocus = (event: Event) => {
    // The control that asked can be a menu item that is gone by now; skip it then.
    if (from.current?.isConnected) {
      event.preventDefault();
      from.current.focus();
    }
  };
  return (
    <ComposerToolsContext.Provider value={value}>
      {children}
      <PostingTimesDrawer
        open={open === "times"}
        onOpenChange={(next) => setOpen(next ? "times" : null)}
        accounts={accounts}
        basics={{ wid, timeZone, now }}
        onCloseAutoFocus={returnFocus}
      />
      <HashtagGroupsDialog
        open={open === "hashtags"}
        onOpenChange={(next) => setOpen(next ? "hashtags" : null)}
        onCloseAutoFocus={returnFocus}
      />
    </ComposerToolsContext.Provider>
  );
}
