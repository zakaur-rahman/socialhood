import { afterEach, describe, expect, it, vi } from "vitest";

import { LEGAL } from "@/lib/legal";
import { GUIDES, guidesUpdated } from "@/lib/marketing/guides";
import { llmsText } from "@/lib/marketing/llms";
import { breadcrumbJsonLd, breadcrumbTrailJsonLd, organizationJsonLd, pageMetadata, verificationMetadata } from "@/lib/marketing/seo";
import { DEFAULT_SITE_URL, PUBLIC_PATHS, siteUrl } from "@/lib/marketing/site";

import { metadata as accessibility } from "./(marketing)/accessibility/page";
import { metadata as cookies } from "./(marketing)/cookies/page";
import { metadata as dpa } from "./(marketing)/dpa/page";
import { metadata as privacy } from "./(marketing)/privacy/page";
import { metadata as refunds } from "./(marketing)/refunds/page";
import { metadata as shipping } from "./(marketing)/shipping/page";
import { metadata as subprocessors } from "./(marketing)/subprocessors/page";
import { metadata as terms } from "./(marketing)/terms/page";
import robots from "./robots";
import sitemap from "./sitemap";

describe("page metadata", () => {
  it("each legal page has its title, description, canonical path and the share image", () => {
    for (const [metadata, title, path] of [
      [privacy, "Privacy Policy", "/privacy"],
      [terms, "Terms of Service", "/terms"],
      [refunds, "Refund and Cancellation Policy", "/refunds"],
      [shipping, "Shipping and Delivery Policy", "/shipping"],
      [subprocessors, "Subprocessors", "/subprocessors"],
      [cookies, "Cookies and Storage", "/cookies"],
      [dpa, "Data Processing Agreement", "/dpa"],
      [accessibility, "Accessibility Statement", "/accessibility"],
    ] as const) {
      expect(metadata.title).toBe(title);
      expect(metadata.description).toBeTruthy();
      expect(metadata.alternates?.canonical).toBe(path);
      expect(metadata.openGraph).toMatchObject({ url: path, title: `${title} · Amplychat`, images: [expect.objectContaining({ url: "/og.png" })] });
      expect(metadata.twitter).toMatchObject({ card: "summary_large_image", images: [expect.objectContaining({ url: "/og.png" })] });
    }
  });

  it("the landing page names itself in full", () => {
    expect(pageMetadata({ title: "Amplychat · X", description: "d", path: "/", absoluteTitle: true }).title).toEqual({
      absolute: "Amplychat · X",
    });
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("site URL", () => {
  it("comes from NEXT_PUBLIC_SITE_URL, as an origin", () => {
    expect(siteUrl("https://www.amplychat.com/some/path/")).toBe("https://www.amplychat.com");
  });

  it("defaults to the apex domain, the canonical origin (C-142)", () => {
    expect(DEFAULT_SITE_URL).toBe("https://amplychat.com");
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
      "https://socialhood.example/pricing",
      "https://socialhood.example/switch-from-manychat",
      "https://socialhood.example/compare/manychat",
      "https://socialhood.example/compare/interakt",
      "https://socialhood.example/compare",
      "https://socialhood.example/compare/linkdm",
      "https://socialhood.example/compare/instantdm",
      "https://socialhood.example/compare/inro",
      "https://socialhood.example/compare/creatorflow",
      "https://socialhood.example/compare/wati",
      "https://socialhood.example/compare/aisensy",
      "https://socialhood.example/compare/spur",
      "https://socialhood.example/features/comment-intelligence",
      "https://socialhood.example/features/ai-inbox",
      "https://socialhood.example/features/publishing",
      "https://socialhood.example/privacy",
      "https://socialhood.example/terms",
      "https://socialhood.example/refunds",
      "https://socialhood.example/shipping",
      "https://socialhood.example/data-deletion",
      "https://socialhood.example/contact",
      "https://socialhood.example/developers/api",
      "https://socialhood.example/security",
      "https://socialhood.example/guides",
      "https://socialhood.example/for-creators",
      "https://socialhood.example/for-businesses",
      "https://socialhood.example/safety",
      "https://socialhood.example/changelog",
      "https://socialhood.example/ai-info",
      "https://socialhood.example/compare",
      "https://socialhood.example/subprocessors",
      "https://socialhood.example/cookies",
      "https://socialhood.example/dpa",
      "https://socialhood.example/accessibility",
      ...GUIDES.map((guide) => `https://socialhood.example/guides/${guide.slug}`),
    ]);
    // C-153: the index takes the newest guide's date, each guide its own updated date.
    expect(entries.find((entry) => entry.url.endsWith("/guides"))?.lastModified).toBe(guidesUpdated());
    for (const guide of GUIDES) {
      expect(entries.find((entry) => entry.url.endsWith(`/guides/${guide.slug}`))?.lastModified).toBe(guide.updated);
    }
    expect(entries.find((entry) => entry.url.endsWith("/privacy"))?.lastModified).toBe("2026-10-29");
    // Every page has an ISO date, never a build time.
    for (const entry of entries) expect(entry.lastModified, entry.url).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(entries.some((entry) => /\/(app|w|sign-in|unsubscribe)\b/.test(entry.url))).toBe(false);
  });

  it("uses the fallback origin without the env", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "");
    expect(sitemap()[0].url).toBe(`${DEFAULT_SITE_URL}/`);
  });
});

describe("/robots.txt", () => {
  it("allows the site, keeps crawlers out of the app, auth, unsubscribe links, dev pages and /api, and names the sitemap", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example");
    const result = robots();
    const rules = Array.isArray(result.rules) ? result.rules : [result.rules];
    expect(rules).toEqual([
      { userAgent: "*", allow: "/", disallow: ["/app$", "/app/", "/w/", "/sign-in", "/sign-up", "/unsubscribe", "/dev/", "/api/"] },
    ]);
    // No public page is disallowed by mistake ("/app$" must not catch /apple-icon.png either).
    const blocked = (path: string) =>
      rules[0].disallow?.length &&
      [rules[0].disallow].flat().some((rule) => (rule.endsWith("$") ? path === rule.slice(0, -1) : path.startsWith(rule)));
    for (const path of [...PUBLIC_PATHS, "/apple-icon.png", "/llms.txt"]) expect(blocked(path), path).toBe(false);
    expect(result.sitemap).toBe("https://socialhood.example/sitemap.xml");
  });
});

describe("verification tags (C-142)", () => {
  it("are left out when no env var is set", () => {
    expect(verificationMetadata({})).toBeUndefined();
    expect(verificationMetadata({ NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION: "  " })).toBeUndefined();
  });

  it("render Google's, Bing's and Meta's tags from their env vars", () => {
    expect(
      verificationMetadata({
        NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION: "g-token",
        NEXT_PUBLIC_BING_SITE_VERIFICATION: "b-token",
        NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION: "f-token",
      }),
    ).toEqual({ google: "g-token", other: { "msvalidate.01": "b-token", "facebook-domain-verification": "f-token" } });
    expect(verificationMetadata({ NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION: "f-token" })).toEqual({
      other: { "facebook-domain-verification": "f-token" },
    });
  });
});

describe("structured data (C-142)", () => {
  it("the Organization names the product, the registered entity, the logo and the support address", () => {
    const org = organizationJsonLd("https://socialhood.example");
    expect(org).toMatchObject({
      "@type": "Organization",
      "@id": "https://socialhood.example/#organization",
      name: "Amplychat",
      url: "https://socialhood.example/",
      logo: "https://socialhood.example/icons/icon-512.png",
      email: "support@amplychat.com",
    });
    if (LEGAL.entityName) expect(org.legalName).toBe(LEGAL.entityName.trim());
    expect(org).not.toHaveProperty("sameAs");
    expect(org).not.toHaveProperty("aggregateRating");
  });

  it("a guide's breadcrumb goes Home, Guides, then the guide (C-153)", () => {
    expect(
      breadcrumbTrailJsonLd(
        [
          { name: "Guides", path: "/guides" },
          { name: "A guide", path: "/guides/a-guide" },
        ],
        "https://socialhood.example",
      ),
    ).toMatchObject({
      itemListElement: [
        { position: 1, item: "https://socialhood.example/" },
        { position: 2, name: "Guides", item: "https://socialhood.example/guides" },
        { position: 3, name: "A guide", item: "https://socialhood.example/guides/a-guide" },
      ],
    });
  });

  it("a breadcrumb goes Home, then the page", () => {
    expect(breadcrumbJsonLd("Pricing", "/pricing", "https://socialhood.example")).toEqual({
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Home", item: "https://socialhood.example/" },
        { "@type": "ListItem", position: 2, name: "Pricing", item: "https://socialhood.example/pricing" },
      ],
    });
  });
});

describe("/llms.txt", () => {
  it("describes the product and links every public page at the site URL", () => {
    const text = llmsText("https://socialhood.example");
    expect(text.startsWith("# Amplychat\n")).toBe(true);
    for (const path of PUBLIC_PATHS) expect(text, path).toContain(`(https://socialhood.example${path === "/" ? "/" : path})`);
    for (const guide of GUIDES) expect(text, guide.slug).toContain(`(https://socialhood.example/guides/${guide.slug})`);
    expect(text).not.toMatch(/undefined|null/);
  });
});

describe("one English site, no Hinglish page (C-155)", () => {
  it("page metadata names only the canonical path, with no hreflang alternates or other locale", () => {
    const metadata = pageMetadata({ title: "Amplychat · X", description: "d", path: "/", absoluteTitle: true });
    expect(metadata.alternates).toEqual({ canonical: "/" });
    expect(metadata.openGraph).not.toHaveProperty("locale");
  });

  it("the sitemap, llms.txt and the guides leave out /hi and the Hinglish guide", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example");
    const entries = sitemap();
    expect(entries.filter((entry) => entry.alternates)).toEqual([]);
    expect(entries.some((entry) => /\/hi$|hinglish/.test(entry.url))).toBe(false);
    expect(llmsText("https://socialhood.example")).not.toMatch(/\/hi\b|hinglish|hindi|india/i);
    expect(GUIDES.some((guide) => guide.slug === "replying-in-hinglish")).toBe(false);
  });
});
