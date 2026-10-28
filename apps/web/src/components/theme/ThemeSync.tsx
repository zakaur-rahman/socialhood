"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { THEMED_ROUTE, applySiteThemeColor } from "@/lib/theme";
import { syncThemeColor, useTheme } from "@/lib/use-theme";

/**
 * Renders nothing: keeps `<meta name="theme-color">` (the browser bar on a phone) on the canvas of
 * the theme on screen. The server renders the dark canvas; this moves it for Light, and for System
 * when the OS is light. On the public pages it is the site's paper, whatever the theme (C-155).
 */
export function ThemeSync() {
  const { resolved } = useTheme();
  const pathname = usePathname();
  useEffect(() => {
    if (pathname && !THEMED_ROUTE.test(pathname)) applySiteThemeColor();
    else syncThemeColor(resolved);
  }, [resolved, pathname]);
  return null;
}
