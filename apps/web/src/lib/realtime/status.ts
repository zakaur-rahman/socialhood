"use client";

import { useEffect, useState } from "react";
import { create } from "zustand";

/**
 * The tab's event stream (TR-FE-04), for the sidebar's "Reconnecting…" notice: connecting until
 * the first open, connected while it is open, reconnecting from a drop until it opens again.
 */
export type RealtimeStatus = "connecting" | "connected" | "reconnecting";

type State = {
  status: RealtimeStatus;
  /** When the status last changed (ms since the epoch). */
  since: number;
  setStatus: (status: RealtimeStatus) => void;
};

export const useRealtimeStore = create<State>((set, get) => ({
  status: "connecting",
  since: 0,
  setStatus: (status) => {
    if (get().status !== status) set({ status, since: Date.now() });
  },
}));

export function setRealtimeStatus(status: RealtimeStatus): void {
  useRealtimeStore.getState().setStatus(status);
}

/**
 * The server ends each stream after 30 minutes and the client is back within about 3 s, so a drop
 * is only worth showing once it has lasted this long.
 */
export const RECONNECTING_GRACE_MS = 5_000;

/** True once the stream has been down for the grace period, until it opens again. */
export function useReconnecting(graceMs = RECONNECTING_GRACE_MS): boolean {
  const status = useRealtimeStore((state) => state.status);
  const since = useRealtimeStore((state) => state.since);
  // The drop (by its start time) the grace period has run out for.
  const [shownFor, setShownFor] = useState<number | null>(null);

  useEffect(() => {
    if (status !== "reconnecting") return;
    const timer = window.setTimeout(() => setShownFor(since), Math.max(0, since + graceMs - Date.now()));
    return () => window.clearTimeout(timer);
  }, [status, since, graceMs]);

  return status === "reconnecting" && shownFor === since;
}
