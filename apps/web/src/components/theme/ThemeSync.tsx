"use client";

import { useEffect } from "react";

import { syncThemeColor, useTheme } from "@/lib/use-theme";

/**
 * Renders nothing: keeps `<meta name="theme-color">` (the browser bar on a phone) on the canvas of
 * the theme on screen. The server renders the dark canvas; this moves it for Light, and for System
 * when the OS is light.
 */
export function ThemeSync() {
  const { resolved } = useTheme();
  useEffect(() => {
    syncThemeColor(resolved);
  }, [resolved]);
  return null;
}
