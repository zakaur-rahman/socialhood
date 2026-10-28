"use client";

import { useLayoutEffect } from "react";

import { SITE_THEME, applySiteThemeColor, applyThemeAttribute, readThemeCookie } from "@/lib/theme";

/**
 * For the public pages (C-155): sets `data-theme` on <html> to the site's light scheme before paint
 * on a client navigation, and gives the user's choice back when the page unmounts. The first load
 * is pinned by the root layout's head script (THEME_INIT_SCRIPT, by route), because this runs only
 * after hydration. The site's colours don't depend on it (the `.site` frame sets its own palette);
 * it keeps the browser's own parts (scrollbars, form controls) and the browser bar on paper.
 */
export function ThemePin() {
  useLayoutEffect(() => {
    applyThemeAttribute(SITE_THEME);
    applySiteThemeColor();
    return () => applyThemeAttribute(readThemeCookie(document.cookie));
  }, []);
  return null;
}
