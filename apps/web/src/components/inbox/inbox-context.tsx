"use client";

import { createContext, useContext } from "react";

import { useMediaQuery } from "@/lib/use-browser-state";

import type { InboxTab } from "./ListHeader";

/**
 * UX-INB-01 widths: ≥ 1280 wide (list 320, details inline 300), 1024–1279 desktop (list 320,
 * details as a sheet), 768–1023 tablet (list 300), < 768 phone (one pane at a time).
 */
export type InboxLayout = "wide" | "desktop" | "tablet" | "phone";

export function useInboxLayout(): InboxLayout {
  const xl = useMediaQuery("(min-width: 1280px)");
  const lg = useMediaQuery("(min-width: 1024px)");
  const md = useMediaQuery("(min-width: 768px)");
  if (xl) return "wide";
  if (lg) return "desktop";
  if (md) return "tablet";
  return "phone";
}

export type InboxUi = {
  layout: InboxLayout;
  slug: string;
  selectedId: string | null;
  detailsOpen: boolean;
  toggleDetails: () => void;
  closeDetails: () => void;
  setTab: (tab: InboxTab) => void;
  /** The user marked this conversation unread: don't mark it read again while it stays open. */
  manualUnreadId: string | null;
  markUnread: (id: string) => void;
  archive: (id: string, archived: boolean) => void;
};

const InboxUiContext = createContext<InboxUi | null>(null);

export const InboxUiProvider = InboxUiContext.Provider;

export function useInboxUi(): InboxUi {
  const value = useContext(InboxUiContext);
  if (!value) throw new Error("useInboxUi must be used inside the inbox");
  return value;
}

/** For components that also render outside the inbox shell (tests, previews). */
export function useOptionalInboxUi(): InboxUi | null {
  return useContext(InboxUiContext);
}
