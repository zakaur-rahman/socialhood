/**
 * Token values for code that can't use CSS variables (C-127), without tokens.ts's descriptions of
 * every token: client components import this (the theme-color sync, the global error page), so the
 * public pages don't download the token catalogue (C-152). tokens.ts re-exports both functions.
 */
import { tokenValues } from "./tokens.generated";

/** The two themes (C-129). Dark is the default. */
export type Theme = "dark" | "light";

/**
 * A colour token's value, for the consumers that can't read CSS variables: Clerk (it computes
 * shades), the OG image (Satori), the manifest and the viewport (UI-ISS-095). They read it here
 * instead of restating the hex, so a token change reaches them too. A chart alias resolves to the
 * token it points at. `theme` picks the dark (default) or light value (C-129); a consumer that follows
 * the user's choice passes the resolved theme, one that is dark on purpose (the OG image, the
 * manifest, the global error page) passes nothing.
 */
export function colorValue(name: string, theme: Theme = "dark"): string {
  const colors = (theme === "light" ? tokenValues.colorsLight : tokenValues.colors) as Record<string, string>;
  const aliases = tokenValues.colorAliases as Record<string, string>;
  const found = colors[name] ?? colors[aliases[name]];
  if (found === undefined) throw new Error(`Unknown colour token: ${name}`);
  return found;
}

/** A radius token's value (`lg` is 0.5rem), for Clerk and the global error page, which can't use `rounded-lg`. */
export function radiusValue(name: string): string {
  const found = (tokenValues.radius as Record<string, string>)[name];
  if (found === undefined) throw new Error(`Unknown radius token: ${name}`);
  return found;
}

