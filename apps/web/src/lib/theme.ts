/**
 * The theme choice (C-102): Dark (the default), Light, or System. The choice lives in a cookie,
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
import { colorValue, type Theme } from "@/styles/tokens";

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
 * Runs in <head> before first paint: copies the cookie to `data-theme`. It must not import
 * anything, so it is a string, built from the cookie name. lib/theme.test.ts runs it.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var m=document.cookie.match(/(?:^|;\\s*)${THEME_COOKIE}=(dark|light|system)/);if(m)document.documentElement.setAttribute("data-theme",m[1])}catch(e){}})()`;

/** Runs at the top of a page that is always dark (the marketing pages): pins <html> before paint. */
export const THEME_PIN_DARK_SCRIPT = `document.documentElement.setAttribute("data-theme","dark")`;
