"use client";

import { useSyncExternalStore } from "react";

/**
 * FR-NOT-03: installing the app. Chromium browsers fire beforeinstallprompt once per page load when
 * the app can be installed; it is kept here so an Install button can show the browser's prompt
 * later. Safari has no such event: iPhone users get the Add to Home Screen steps instead.
 */
type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferred: InstallPromptEvent | null = null;
let listening = false;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

/** Start listening as early as possible: the event can fire before any component mounts. */
export function captureInstallPrompt(target: Window | undefined = typeof window === "undefined" ? undefined : window) {
  if (!target || listening) return;
  listening = true;
  target.addEventListener("beforeinstallprompt", (event) => {
    // Our own prompt replaces the browser's mini-infobar; it can be dismissed and stays dismissed.
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    emit();
  });
  target.addEventListener("appinstalled", () => {
    deferred = null;
    emit();
  });
}

captureInstallPrompt();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Whether the browser's install prompt is available, and a function that shows it. */
export function useInstallPrompt(): { available: boolean; install: () => Promise<boolean> } {
  const event = useSyncExternalStore(
    subscribe,
    () => deferred,
    () => null,
  );
  return {
    available: event !== null,
    install: async () => {
      const current = deferred;
      if (!current) return false;
      await current.prompt();
      const choice = await current.userChoice;
      // A prompt can be shown once; the browser fires the event again if it may ask again.
      deferred = null;
      emit();
      return choice.outcome === "accepted";
    },
  };
}

/** Test hook: forget any captured prompt. */
export function resetInstallPrompt() {
  deferred = null;
  emit();
}
