"use client";

import { useCallback, useSyncExternalStore } from "react";

import { useMediaQuery } from "@/lib/use-browser-state";
import {
  DEFAULT_THEME,
  applyThemeAttribute,
  applyThemeColor,
  parseTheme,
  resolveChoice,
  writeThemeCookie,
  type ThemeChoice,
} from "@/lib/theme";
import type { Theme } from "@/styles/tokens";

const listeners = new Set<() => void>();

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

/** The choice on screen: the attribute the head script (or the pin) set on <html>. */
function currentChoice(): ThemeChoice {
  return parseTheme(document.documentElement.getAttribute("data-theme"));
}

/**
 * The theme choice and what it resolves to, for the few things CSS can't do: the switch itself,
 * the `theme-color` meta, and Clerk's appearance (a JS object). System resolves by the OS
 * setting and follows a change of it. The server value is Dark, what the HTML is rendered with.
 */
export function useTheme(): { choice: ThemeChoice; resolved: Theme; setChoice: (choice: ThemeChoice) => void } {
  const choice = useSyncExternalStore(subscribe, currentChoice, () => DEFAULT_THEME);
  // Dark on the server and during hydration: that is what the HTML was rendered with.
  const prefersLight = useMediaQuery("(prefers-color-scheme: light)", false);
  const resolved = resolveChoice(choice, prefersLight);
  const setChoice = useCallback((next: ThemeChoice) => {
    writeThemeCookie(next);
    applyThemeAttribute(next);
    for (const listener of listeners) listener();
  }, []);
  return { choice, resolved, setChoice };
}

/** Keeps the browser chrome colour on the theme on screen (see ThemeSync). */
export function syncThemeColor(resolved: Theme): void {
  applyThemeColor(resolved);
}
