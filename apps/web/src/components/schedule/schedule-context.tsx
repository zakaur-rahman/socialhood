"use client";

import type { Route } from "next";
import { createContext, useContext } from "react";

import type { ScheduledPostSummary, SocialAccount } from "@/lib/api/types";
import { UNKNOWN_ACCOUNT_COLOR, type AccountColor } from "@/lib/schedule/format";

/** What a post card can ask the page to do; each opens its own dialog or calls the API. */
export type PostActions = {
  /** "Move to…" for a scheduled post, "Schedule for…" for a draft (FR-PUB-08's keyboard and phone path). */
  moveTo: (post: ScheduledPostSummary, returnFocus?: HTMLElement | null, day?: string) => void;
  queue: (post: ScheduledPostSummary) => void;
  unschedule: (post: ScheduledPostSummary) => void;
  duplicate: (post: ScheduledPostSummary) => void;
  remove: (post: ScheduledPostSummary, returnFocus?: HTMLElement | null) => void;
  /** New post at a clicked time (F-13), or with no time. */
  newPostAt: (at: Date | null) => void;
};

export type ScheduleContextValue = {
  wid: string;
  slug: string;
  timeZone: string;
  now: Date;
  accounts: Map<string, SocialAccount>;
  colors: Map<string, AccountColor>;
  actions: PostActions;
  /** The composer, built at /schedule/{id} (UX-SCR-13). */
  composerHref: (post: Pick<ScheduledPostSummary, "id">) => Route;
  /** Posts that have a request in flight: their menus wait. */
  busyIds: ReadonlySet<string>;
};

const ScheduleContext = createContext<ScheduleContextValue | null>(null);

export const ScheduleProvider = ScheduleContext.Provider;

export function useSchedule(): ScheduleContextValue {
  const value = useContext(ScheduleContext);
  if (!value) throw new Error("useSchedule must be used inside the Schedule page");
  return value;
}

export function accountColor(value: ScheduleContextValue, accountId: string | null | undefined): AccountColor {
  return (accountId && value.colors.get(accountId)) || UNKNOWN_ACCOUNT_COLOR;
}
