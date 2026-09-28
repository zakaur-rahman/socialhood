"use client";

import { useCallback, useSyncExternalStore } from "react";

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

/** A remembered boolean, per browser (for example the sidebar's collapsed state). */
export function useStoredFlag(key: string, fallback = false): [boolean, (value: boolean) => void] {
  const subscribe = useCallback((onChange: () => void) => {
    window.addEventListener("storage", onChange);
    window.addEventListener(LOCAL_EVENT, onChange);
    return () => {
      window.removeEventListener("storage", onChange);
      window.removeEventListener(LOCAL_EVENT, onChange);
    };
  }, []);
  const value = useSyncExternalStore(
    subscribe,
    () => {
      const stored = read(key);
      return stored === null ? fallback : stored === "1";
    },
    () => fallback,
  );
  const set = useCallback(
    (next: boolean) => {
      try {
        window.localStorage.setItem(key, next ? "1" : "0");
      } catch {
        // Not remembered, but still applied for this page view below.
      }
      window.dispatchEvent(new Event(LOCAL_EVENT));
    },
    [key],
  );
  return [value, set];
}
