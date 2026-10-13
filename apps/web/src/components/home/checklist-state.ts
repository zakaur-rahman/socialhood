"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * "You're all set" shows once per session (UI-058, UI-ISS-084). Two small flags per workspace say
 * where we are: sessionStorage remembers it was shown in this tab's session, localStorage that it
 * was shown at all. Seen before but not in this session means hidden; "Show setup checklist" in
 * the workspace menu clears both. Storage can be blocked, so every access is guarded and falls
 * back to memory for this page view.
 */
export type AllSetPhase = "fresh" | "session" | "past";

const EVENT = "socialhood:checklist-all-set";
const key = (workspaceId: string) => `socialhood:checklist-all-set:${workspaceId}`;

// Only used where storage throws (blocked, private mode): the flags then last for this page view.
const memory = { local: new Set<string>(), session: new Set<string>() };

function storageOf(kind: "local" | "session"): Storage {
  return kind === "local" ? window.localStorage : window.sessionStorage;
}

function has(kind: "local" | "session", name: string): boolean {
  try {
    return storageOf(kind).getItem(name) === "1";
  } catch {
    return memory[kind].has(name);
  }
}

function put(kind: "local" | "session", name: string) {
  try {
    storageOf(kind).setItem(name, "1");
  } catch {
    memory[kind].add(name);
  }
}

function drop(kind: "local" | "session", name: string) {
  memory[kind].delete(name);
  try {
    storageOf(kind).removeItem(name);
  } catch {
    // Nothing stored to clear.
  }
}

function phaseOf(workspaceId: string): AllSetPhase {
  const name = key(workspaceId);
  if (has("session", name)) return "session";
  if (has("local", name)) return "past";
  return "fresh";
}

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

/** `fresh`: never shown; `session`: shown in this session (keep showing); `past`: hide. */
export function useAllSetPhase(workspaceId: string): AllSetPhase {
  return useSyncExternalStore(
    subscribe,
    useCallback(() => phaseOf(workspaceId), [workspaceId]),
    () => "fresh" as const,
  );
}

/** The all-set card has been shown: keep it for this session, hide it in the next. */
export function markAllSetShown(workspaceId: string) {
  put("local", key(workspaceId));
  put("session", key(workspaceId));
  window.dispatchEvent(new Event(EVENT));
}

/** "Show setup checklist": forget that the all-set card was shown. */
export function resetAllSet(workspaceId: string) {
  drop("local", key(workspaceId));
  drop("session", key(workspaceId));
  window.dispatchEvent(new Event(EVENT));
}
