"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";

/** A media query as React state; the server snapshot assumes a desktop screen. */
export function useMediaQuery(query: string, serverValue = true): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => serverValue,
  );
}

const LOCAL_EVENT = "socialhood:local-storage";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // private mode or blocked storage
  }
}

function subscribeStorage(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(LOCAL_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(LOCAL_EVENT, onChange);
  };
}

// Values written where storage is blocked still apply for this page view.
const memory = new Map<string, string>();

function write(key: string, value: string) {
  memory.set(key, value);
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Not remembered across visits.
  }
  window.dispatchEvent(new Event(LOCAL_EVENT));
}

/** A remembered boolean, per browser (for example the sidebar's collapsed state). */
export function useStoredFlag(key: string, fallback = false): [boolean, (value: boolean) => void] {
  const value = useSyncExternalStore(
    subscribeStorage,
    () => {
      const stored = read(key) ?? memory.get(key) ?? null;
      return stored === null ? fallback : stored === "1";
    },
    () => fallback,
  );
  const set = useCallback((next: boolean) => write(key, next ? "1" : "0"), [key]);
  return [value, set];
}

/** A remembered string, per browser. Read synchronously, so the first paint already uses it. */
export function useStoredString<T extends string>(key: string, fallback: T): [T | string, (value: T) => void] {
  const value = useSyncExternalStore(
    subscribeStorage,
    () => read(key) ?? memory.get(key) ?? fallback,
    () => fallback,
  );
  const set = useCallback((next: T) => write(key, next), [key]);
  return [value, set];
}

/** The current time, refreshed every interval (list times, window chips). */
export function useNow(intervalMs = 60_000): Date {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const timer = window.setInterval(onChange, intervalMs);
      return () => window.clearInterval(timer);
    },
    [intervalMs],
  );
  // The snapshot must be stable between ticks, so it is the time rounded down to the interval.
  const snapshot = useCallback(() => Math.floor(Date.now() / intervalMs) * intervalMs, [intervalMs]);
  const time = useSyncExternalStore(subscribe, snapshot, snapshot);
  return useMemo(() => new Date(time), [time]);
}
