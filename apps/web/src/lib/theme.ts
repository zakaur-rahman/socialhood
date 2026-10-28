/**
 * The theme choice (C-129): Dark (the default), Light, or System. The choice lives in a cookie,
 * `sh_theme`, so it survives sessions and a script can read it before the first paint; it is
 * applied as `data-theme` on <html>, which globals.css turns into `color-scheme` (the tokens are
 * `light-dark()` pairs, so nothing else changes). System sets both schemes and the browser follows
 * the OS with no script and no listener.
 *
 * Why a script and not a server read: the root layout is shared with the static marketing pages
 * (revalidated hourly), and `cookies()` there would make every page dynamic. The CSP already
 * allows inline scripts (lib/security/headers.ts), so a small script in <head> sets the attribute
 * before anything paints. No cookie, or Dark, leaves the server-rendered default.
 */
import { colorValue, type Theme } from "@/styles/token-values";

export const THEME_COOKIE = "sh_theme";
export const THEME_CHOICES = ["dark", "light", "system"] as const;
export type ThemeChoice = (typeof THEME_CHOICES)[number];
export const DEFAULT_THEME: ThemeChoice = "dark";
const ONE_YEAR = 60 * 60 * 24 * 365;

/** Labels for the switch, in its order. */
export const THEME_LABEL: Record<ThemeChoice, string> = { dark: "Dark", light: "Light", system: "System" };

/** A cookie or attribute value as a choice; anything unknown is the default. */
export function parseTheme(value: string | null | undefined): ThemeChoice {
  return THEME_CHOICES.find((choice) => choice === value) ?? DEFAULT_THEME;
}

/** The theme a choice shows, given whether the OS prefers light. */
export function resolveChoice(choice: ThemeChoice, prefersLight: boolean): Theme {
  if (choice === "system") return prefersLight ? "light" : "dark";
  return choice;
}

/** The saved choice from a `document.cookie` string. */
export function readThemeCookie(cookie: string): ThemeChoice {
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${THEME_COOKIE}=([^;]*)`));
  return parseTheme(match?.[1]);
}

/** Saves the choice for a year, for the whole site. Not HttpOnly: the script reads it. */
export function writeThemeCookie(choice: ThemeChoice): void {
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${THEME_COOKIE}=${choice}; path=/; max-age=${ONE_YEAR}; samesite=lax${secure}`;
}

/** Sets `data-theme` on <html> (or another root, for tests). */
export function applyThemeAttribute(choice: ThemeChoice, root: HTMLElement = document.documentElement): void {
  root.setAttribute("data-theme", choice);
}

/** Points the browser chrome (`theme-color`) at the canvas of the theme on screen. */
export function applyThemeColor(theme: Theme, doc: Document = document): void {
  for (const meta of doc.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    meta.content = colorValue("canvas", theme);
    meta.removeAttribute("media");
  }
}

/**
 * The routes that follow the member's theme: the app, sign-in and sign-up, and the dev pages.
 * Every other page (the public site and its 404) is always dark (C-129). app/layout.test.ts keeps
 * this in step with the (app), (auth), (dev) and (marketing) route folders.
 */
export const THEMED_ROUTE = /^\/(app|w|sign-in|sign-up|dev)(\/|$)/;

/**
 * Runs in <head> before first paint: on a themed route, copies the cookie to `data-theme`; on any
 * other page, pins it dark. It must not import anything, so it is a string, built from the cookie
 * name and THEMED_ROUTE. lib/theme.test.ts runs it. (It replaces an inline script in the marketing
 * layout, which React refused to render on a client navigation; ThemePin covers those.)
 * The regex's `\\s` is doubled: in a template literal `\s` becomes a bare "s", and the script then
 * found the cookie only when it came first (C-150; Clerk's cookies come first in production).
 */
export const THEME_INIT_SCRIPT = `(function(){try{var d=document.documentElement;if(!${THEMED_ROUTE}.test(location.pathname)){d.setAttribute("data-theme","dark");return}var m=document.cookie.match(/(?:^|;\\s*)${THEME_COOKIE}=(dark|light|system)/);if(m)d.setAttribute("data-theme",m[1])}catch(e){}})()`;
