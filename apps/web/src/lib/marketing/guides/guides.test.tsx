import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DESCRIPTION_MAX, TITLE_MAX, articleJsonLd } from "../seo";
import { SITE_NAME } from "../site";
import { guidesFeed } from "./feed";
import { GUIDES, GUIDE_AUTHOR, findGuide, guidePath, guidesUpdated } from "./index";

const ISO = /^\d{4}-\d{2}-\d{2}$/;

/** The body's text, as a reader sees it. */
function bodyText(Body: ComponentType): string {
  return renderToStaticMarkup(createElement(Body))
    .replace(/<[^>]+>/g, " ")
    .replace(/&[a-z#0-9]+;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function words(text: string): number {
  return text.split(" ").filter((word) => /\w/.test(word)).length;
}

describe("the guides (C-153)", () => {
  it("are newest first, with unique slugs", () => {
    const published = GUIDES.map((guide) => guide.published);
    expect([...published].sort().reverse()).toEqual(published);
    expect(new Set(GUIDES.map((guide) => guide.slug)).size).toBe(GUIDES.length);
    expect(GUIDES.length).toBeGreaterThanOrEqual(4);
  });

  it.each(GUIDES.map((guide) => [guide.slug, guide] as const))("%s: metadata fits search results", (slug, guide) => {
    expect(slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    expect(`${guide.title} · ${SITE_NAME}`.length, guide.title).toBeLessThanOrEqual(TITLE_MAX);
    expect(guide.description.length, guide.description).toBeGreaterThanOrEqual(50);
    expect(guide.description.length, guide.description).toBeLessThanOrEqual(DESCRIPTION_MAX);
    expect(guide.published).toMatch(ISO);
    expect(guide.updated).toMatch(ISO);
    expect(guide.updated >= guide.published).toBe(true);
    expect(guide.author).toBe(GUIDE_AUTHOR);
    expect(guide.tags.length).toBeGreaterThan(0);
    expect(findGuide(slug)).toBe(guide);
  });

  it.each(GUIDES.map((guide) => [guide.slug, guide] as const))("%s: 900 to 1,500 words, and the reading time says so", (_, guide) => {
    const count = words(bodyText(guide.Body));
    expect(count).toBeGreaterThanOrEqual(900);
    expect(count).toBeLessThanOrEqual(1500);
    expect(guide.readingMinutes, `${count} words`).toBe(Math.round(count / 200));
  });

  it.each(GUIDES.map((guide) => [guide.slug, guide] as const))("%s: copy rules (sentence case headings, no please, the product name)", (_, guide) => {
    const html = renderToStaticMarkup(createElement(guide.Body));
    const text = bodyText(guide.Body);
    expect(text).not.toMatch(/\bplease\b/i);
    expect(text).not.toMatch(/Social Hood/);
    // No h1 in a body: the page has one, the guide's h1.
    expect(html).not.toMatch(/<h1/);
    // Headings in sentence case: no word after the first starts with a capital unless it is a name.
    const NAMES = /^(Instagram|Instagram's|WhatsApp|DM|DMs|Meta|Meta's|India|India's|Indian|Hindi|Hinglish|English|Pro|Auto|Suggest|Off|Interakt|Manychat|Razorpay|LINK|AI|API|I|Amplychat|Amplychat's|Tamil|Bengali|Marathi)$/;
    for (const [, heading] of html.matchAll(/<h[23][^>]*>(.*?)<\/h[23]>/g)) {
      const plain = heading.replace(/<[^>]+>/g, "").replace(/&#x27;|&apos;/g, "'");
      const later = plain.split(/\s+/).slice(1);
      for (const word of later) {
        const bare = word.replace(/[^\w']/g, "");
        if (/^[A-Z]/.test(bare)) expect(bare, plain).toMatch(NAMES);
      }
    }
    // Internal links go to pages that exist.
    for (const [, href] of html.matchAll(/href="(\/[^"#]*)"/g)) {
      expect(["/features/ai-inbox", "/features/comment-intelligence", "/pricing", "/compare/interakt", "/switch-from-manychat", "/hi", ...GUIDES.map((g) => guidePath(g.slug))]).toContain(href);
    }
  });

  it("each guide's structured data names the article, its dates, author and publisher", () => {
    for (const guide of GUIDES) {
      const data = articleJsonLd(
        {
          path: guidePath(guide.slug),
          title: guide.title,
          description: guide.description,
          published: guide.published,
          updated: guide.updated,
          author: guide.author,
          tags: guide.tags,
          faq: guide.faq,
        },
        "https://socialhood.example",
      );
      expect(data["@context"]).toBe("https://schema.org");
      const graph = data["@graph"] as Record<string, unknown>[];
      const article = graph.find((node) => node["@type"] === "Article") as Record<string, unknown>;
      expect(article).toMatchObject({
        headline: guide.title,
        description: guide.description,
        url: `https://socialhood.example/guides/${guide.slug}`,
        datePublished: guide.published,
        dateModified: guide.updated,
        author: { "@type": "Organization", name: `${SITE_NAME} team` },
        publisher: { "@type": "Organization", name: SITE_NAME },
        image: "https://socialhood.example/og.png",
      });
      expect((article.headline as string).length).toBeLessThanOrEqual(110);
      const faq = graph.find((node) => node["@type"] === "FAQPage");
      if (guide.faq?.length) {
        expect(faq).toMatchObject({ "@id": `https://socialhood.example/guides/${guide.slug}#faq` });
        expect((faq?.mainEntity as unknown[]).length).toBe(guide.faq.length);
      } else {
        expect(faq).toBeUndefined();
      }
    }
  });

  it("the RSS feed lists every guide with its link and date", () => {
    const xml = guidesFeed(GUIDES, "https://socialhood.example");
    expect(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>')).toBe(true);
    expect(xml).toContain("<link>https://socialhood.example/guides</link>");
    expect(xml).toContain('href="https://socialhood.example/guides/rss.xml"');
    for (const guide of GUIDES) expect(xml).toContain(`<link>https://socialhood.example/guides/${guide.slug}</link>`);
    expect(xml.match(/<item>/g)?.length).toBe(GUIDES.length);
    expect(xml).not.toMatch(/undefined|null|Invalid Date/);
    expect(guidesUpdated()).toMatch(ISO);
  });
});
