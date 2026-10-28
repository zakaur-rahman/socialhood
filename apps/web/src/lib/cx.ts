/**
 * Joins class names, skipping the empty ones, without `cn`'s conflict rules (C-152). For the public
 * site's client components only, where no call site overrides a class: `cn` brings its merge
 * tables (about 30 KB compressed) into the browser with the first client component that imports
 * it, and the public pages otherwise load none. Anywhere a className may override a default, use
 * `cn` from lib/utils.
 */
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
