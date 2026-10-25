"use client";

import { useLayoutEffect } from "react";

import { applyThemeAttribute, readThemeCookie } from "@/lib/theme";

/**
 * For a page that is always dark (the marketing pages): sets `data-theme="dark"` on <html> before
 * paint on a client navigation, and gives the user's choice back when the page unmounts. The first
 * load is pinned by an inline script in the layout (THEME_PIN_DARK_SCRIPT), because this runs only
 * after hydration. The subtree also carries `scheme-dark`, so its colours are dark even for the
 * moment before either runs.
 */
export function ThemePin() {
  useLayoutEffect(() => {
    applyThemeAttribute("dark");
    return () => applyThemeAttribute(readThemeCookie(document.cookie));
  }, []);
  return null;
}
