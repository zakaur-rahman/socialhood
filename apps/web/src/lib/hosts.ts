/**
 * Which host serves which page (C-146). One Next.js deployment answers for both the public site
 * (NEXT_PUBLIC_SITE_URL, https://amplychat.com) and the signed-in app (NEXT_PUBLIC_APP_URL,
 * https://dashboard.amplychat.com). The proxy (src/proxy.ts) asks `hostRoute` what to do with each
 * request before Clerk runs:
 *
 * - site host: app pages move to the same path on the app host (308, query kept);
 * - app host: `/` goes to `/app`, robots.txt disallows everything, there is no sitemap, and every
 *   public page moves to the same path on the site (308);
 * - both: shared files (/_next, icons, the manifest, sw.js, /.well-known, og.png) are served as
 *   they are. Most never reach the proxy at all (its matcher skips static files).
 *
 * With NEXT_PUBLIC_APP_URL unset (local dev, e2e, CI) there is one origin and nothing moves.
 */

import { appOrigin, siteUrl } from "@/lib/marketing/site";

/** Pages that belong to the app: the signed-in app, Clerk's pages and the dev-only pages. */
const APP_PREFIXES = ["/app", "/w", "/sign-in", "/sign-up", "/dev"] as const;

/** Served on either host: framework files, icons, the manifest, the service worker, well-known files. */
const SHARED_PREFIXES = [
  "/_next",
  "/icons",
  "/.well-known",
  "/manifest.webmanifest",
  "/sw.js",
  "/favicon.ico",
  "/apple-icon.png",
  "/og.png",
  "/grain.jpg",
] as const;

/** robots.txt on the app host: nothing there is for search engines (its pages are noindex too). */
export const APP_ROBOTS_TXT = "User-agent: *\nDisallow: /\n";

export type HostRoute =
  | { kind: "pass"; host: "single" | "site" | "app" }
  | { kind: "redirect"; location: string; status: 307 | 308 }
  | { kind: "robots" }
  | { kind: "not-found" };

function underAny(pathname: string, prefixes: readonly string[]): boolean {
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function isAppPath(pathname: string): boolean {
  return underAny(pathname, APP_PREFIXES);
}

export function isSharedPath(pathname: string): boolean {
  return underAny(pathname, SHARED_PREFIXES);
}

/** "host[:port]" in lower case, the way URL.host writes it. */
function normalHost(host: string | null | undefined): string {
  return (host ?? "").trim().toLowerCase();
}

/**
 * What to do with a request for `pathname` + `search` (the raw query, "?a=1" or "") that arrived
 * for `host` (the Host header). `app` and `site` are the two origins; `app` null means one origin.
 */
export function hostRoute(
  host: string | null | undefined,
  pathname: string,
  search: string,
  app: string | null = appOrigin(),
  site: string = siteUrl(),
): HostRoute {
  if (!app) return { kind: "pass", host: "single" };
  const onApp = normalHost(host) === new URL(app).host;

  if (!onApp) {
    if (isAppPath(pathname)) return { kind: "redirect", location: `${app}${pathname}${search}`, status: 308 };
    return { kind: "pass", host: "site" };
  }

  if (pathname === "/") return { kind: "redirect", location: `${app}/app${search}`, status: 307 };
  if (pathname === "/robots.txt") return { kind: "robots" };
  if (pathname === "/sitemap.xml") return { kind: "not-found" };
  if (isAppPath(pathname) || isSharedPath(pathname)) return { kind: "pass", host: "app" };
  return { kind: "redirect", location: `${site}${pathname}${search}`, status: 308 };
}
