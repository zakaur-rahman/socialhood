import { afterEach, describe, expect, it, vi } from "vitest";

import { pageMetadata } from "@/lib/marketing/seo";
import { DEFAULT_SITE_URL, siteUrl } from "@/lib/marketing/site";

import { metadata as privacy } from "./(marketing)/privacy/page";
import { metadata as refunds } from "./(marketing)/refunds/page";
import { metadata as terms } from "./(marketing)/terms/page";
import robots from "./robots";
import sitemap from "./sitemap";

describe("page metadata", () => {
  it("each legal page has its title, description, canonical path and the share image", () => {
    for (const [metadata, title, path] of [
      [privacy, "Privacy Policy", "/privacy"],
      [terms, "Terms of Service", "/terms"],
      [refunds, "Refund Policy", "/refunds"],
    ] as const) {
      expect(metadata.title).toBe(title);
      expect(metadata.description).toBeTruthy();
      expect(metadata.alternates?.canonical).toBe(path);
      expect(metadata.openGraph).toMatchObject({ url: path, title: `${title} · Social Hood`, images: [expect.objectContaining({ url: "/og.png" })] });
      expect(metadata.twitter).toMatchObject({ card: "summary_large_image", images: [expect.objectContaining({ url: "/og.png" })] });
    }
  });

  it("the landing page names itself in full", () => {
    expect(pageMetadata({ title: "Social Hood · X", description: "d", path: "/", absoluteTitle: true }).title).toEqual({
      absolute: "Social Hood · X",
    });
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("site URL", () => {
  it("comes from NEXT_PUBLIC_SITE_URL, as an origin", () => {
    expect(siteUrl("https://www.socialhood.com/some/path/")).toBe("https://www.socialhood.com");
  });

  it("falls back when unset or not a URL", () => {
    expect(siteUrl(undefined)).toBe(DEFAULT_SITE_URL);
    expect(siteUrl("socialhood")).toBe(DEFAULT_SITE_URL);
    expect(siteUrl("javascript:alert(1)")).toBe(DEFAULT_SITE_URL);
  });
});

describe("/sitemap.xml", () => {
  it("lists the marketing and legal pages at the site URL", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example");
    const entries = sitemap();
    expect(entries.map((entry) => entry.url)).toEqual([
      "https://socialhood.example/",
      "https://socialhood.example/privacy",
      "https://socialhood.example/terms",
      "https://socialhood.example/refunds",
      "https://socialhood.example/data-deletion",
    ]);
    expect(entries.find((entry) => entry.url.endsWith("/privacy"))?.lastModified).toBe("2026-10-01");
    expect(entries.some((entry) => /\/(app|w|sign-in|unsubscribe)\b/.test(entry.url))).toBe(false);
  });

  it("uses the fallback origin without the env", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "");
    expect(sitemap()[0].url).toBe(`${DEFAULT_SITE_URL}/`);
  });
});

describe("/robots.txt", () => {
  it("allows the site, keeps crawlers out of the app, sign-in and unsubscribe links, and names the sitemap", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example");
    const result = robots();
    const rules = Array.isArray(result.rules) ? result.rules : [result.rules];
    expect(rules).toEqual([
      { userAgent: "*", allow: "/", disallow: ["/app$", "/app/", "/w/", "/sign-in", "/unsubscribe"] },
    ]);
    expect(result.sitemap).toBe("https://socialhood.example/sitemap.xml");
  });
});
