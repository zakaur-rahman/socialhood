import { describe, expect, it } from "vitest";

import { APP_ROBOTS_TXT, hostRoute, isAppPath, isSharedPath } from "./hosts";
import { appOrigin, appUrl, siteHref } from "./marketing/site";

const SITE = "https://amplychat.com";
const APP = "https://dashboard.amplychat.com";

describe("hostRoute (C-146)", () => {
  it("moves nothing while NEXT_PUBLIC_APP_URL is unset (one origin)", () => {
    for (const path of ["/", "/app", "/w/maple/inbox", "/sign-in", "/pricing", "/robots.txt", "/sitemap.xml"]) {
      expect(hostRoute("localhost:3000", path, "", null, SITE)).toEqual({ kind: "pass", host: "single" });
      expect(hostRoute("dashboard.amplychat.com", path, "", null, SITE)).toEqual({ kind: "pass", host: "single" });
    }
  });

  it("sends app pages on the site host to the app host, keeping the path and query (308)", () => {
    const cases: [string, string, string][] = [
      ["/app", "", `${APP}/app`],
      ["/app", "?next=settings/notifications", `${APP}/app?next=settings/notifications`],
      ["/w/maple/inbox", "?c=1", `${APP}/w/maple/inbox?c=1`],
      ["/sign-in", "", `${APP}/sign-in`],
      ["/sign-in/factor-one", "", `${APP}/sign-in/factor-one`],
      ["/sign-up", "?redirect_url=%2Fapp%3Fplan%3Dpro", `${APP}/sign-up?redirect_url=%2Fapp%3Fplan%3Dpro`],
      ["/dev/tokens", "", `${APP}/dev/tokens`],
    ];
    for (const [path, search, location] of cases) {
      expect(hostRoute("amplychat.com", path, search, APP, SITE)).toEqual({ kind: "redirect", location, status: 308 });
    }
  });

  it("serves public pages, robots and the sitemap on the site host", () => {
    for (const path of ["/", "/pricing", "/privacy", "/unsubscribe", "/data-deletion", "/robots.txt", "/sitemap.xml", "/llms.txt", "/apple-icon.png"]) {
      expect(hostRoute("amplychat.com", path, "", APP, SITE)).toEqual({ kind: "pass", host: "site" });
    }
  });

  it("sends the app host's home to /app (signed out, /app goes on to sign-in)", () => {
    expect(hostRoute("dashboard.amplychat.com", "/", "", APP, SITE)).toEqual({ kind: "redirect", location: `${APP}/app`, status: 307 });
    expect(hostRoute("dashboard.amplychat.com", "/", "?plan=pro", APP, SITE)).toEqual({
      kind: "redirect",
      location: `${APP}/app?plan=pro`,
      status: 307,
    });
  });

  it("sends public pages on the app host to the site (308)", () => {
    for (const path of ["/pricing", "/privacy", "/terms", "/data-deletion", "/unsubscribe", "/contact", "/llms.txt", "/no-such-page"]) {
      expect(hostRoute("dashboard.amplychat.com", path, "?code=abc", APP, SITE)).toEqual({
        kind: "redirect",
        location: `${SITE}${path}?code=abc`,
        status: 308,
      });
    }
  });

  it("keeps app pages and shared files on the app host", () => {
    for (const path of ["/app", "/w/maple/settings/billing", "/sign-in", "/sign-up", "/_next/static/x.js", "/icons/icon-192.png", "/manifest.webmanifest", "/sw.js", "/.well-known/security.txt", "/favicon.ico", "/og.png"]) {
      expect(hostRoute("dashboard.amplychat.com", path, "", APP, SITE)).toEqual({ kind: "pass", host: "app" });
    }
  });

  it("answers robots.txt with disallow-all and has no sitemap on the app host", () => {
    expect(hostRoute("dashboard.amplychat.com", "/robots.txt", "", APP, SITE)).toEqual({ kind: "robots" });
    expect(APP_ROBOTS_TXT).toBe("User-agent: *\nDisallow: /\n");
    expect(hostRoute("dashboard.amplychat.com", "/sitemap.xml", "", APP, SITE)).toEqual({ kind: "not-found" });
  });

  it("matches the host without regard to case, and with its port", () => {
    expect(hostRoute("Dashboard.Amplychat.com", "/pricing", "", APP, SITE)).toMatchObject({ kind: "redirect", location: `${SITE}/pricing` });
    const local = "http://dashboard.localhost:3100";
    expect(hostRoute("dashboard.localhost:3100", "/pricing", "", local, "http://localhost:3100")).toMatchObject({
      location: "http://localhost:3100/pricing",
    });
    expect(hostRoute("localhost:3100", "/app", "", local, "http://localhost:3100")).toMatchObject({ location: `${local}/app` });
    // No Host header: treated as the site.
    expect(hostRoute(null, "/app", "", APP, SITE)).toMatchObject({ kind: "redirect", location: `${APP}/app` });
  });

  it("tells app paths by whole segments, so /apple-icon.png and /application are not the app", () => {
    expect(isAppPath("/app")).toBe(true);
    expect(isAppPath("/app/")).toBe(true);
    expect(isAppPath("/apple-icon.png")).toBe(false);
    expect(isAppPath("/application")).toBe(false);
    expect(isAppPath("/workshop")).toBe(false);
    expect(isAppPath("/sign-inside")).toBe(false);
    expect(isSharedPath("/iconsx")).toBe(false);
  });
});

describe("appOrigin, appUrl and siteHref (C-146)", () => {
  it("has no app origin when unset, invalid, not http(s) or the site's own origin", () => {
    expect(appOrigin(undefined, SITE)).toBeNull();
    expect(appOrigin("", SITE)).toBeNull();
    expect(appOrigin("not a url", SITE)).toBeNull();
    expect(appOrigin("ftp://dashboard.amplychat.com", SITE)).toBeNull();
    expect(appOrigin("https://amplychat.com/", SITE)).toBeNull();
  });

  it("takes the origin of the app URL", () => {
    expect(appOrigin("https://dashboard.amplychat.com/", SITE)).toBe(APP);
    expect(appOrigin("https://dashboard.amplychat.com/app?x=1", SITE)).toBe(APP);
  });

  it("keeps links relative on one origin", () => {
    expect(appUrl("/sign-up", null)).toBe("/sign-up");
    expect(appUrl("/sign-up?redirect_url=%2Fapp", null)).toBe("/sign-up?redirect_url=%2Fapp");
    expect(siteHref("/privacy", null)).toBe("/privacy");
  });

  it("makes app links absolute on the app host and public links absolute on the site", () => {
    expect(appUrl("/sign-up", APP)).toBe(`${APP}/sign-up`);
    expect(appUrl("/sign-up?redirect_url=%2Fapp%3Fplan%3Dpro", APP)).toBe(`${APP}/sign-up?redirect_url=%2Fapp%3Fplan%3Dpro`);
    expect(appUrl("/app?next=settings/notifications", APP)).toBe(`${APP}/app?next=settings/notifications`);
    // The site is NEXT_PUBLIC_SITE_URL, unset in tests: the canonical apex.
    expect(siteHref("/privacy", APP)).toBe(`${SITE}/privacy`);
    expect(siteHref("/", APP)).toBe(`${SITE}/`);
  });
});
