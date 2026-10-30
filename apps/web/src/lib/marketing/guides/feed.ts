import { SITE_NAME, absoluteUrl, siteUrl } from "../site";
import { GUIDES, guidesUpdated } from "./index";
import { GUIDES_FEED_PATH, GUIDES_PATH, guidePath, type Guide } from "./types";

function escapeXml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

/** RFC 822 date for RSS, at midnight UTC on the ISO day. */
function rssDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toUTCString();
}

/**
 * /guides/rss.xml (C-153): RSS 2.0 with each guide's title, link, description, date and topics.
 * Descriptions only, not the full text: readers come to the page.
 */
export function guidesFeed(guides: readonly Guide[] = GUIDES, origin: string = siteUrl()): string {
  const items = guides.map((guide) => {
    const url = absoluteUrl(guidePath(guide.slug), origin);
    return [
      "    <item>",
      `      <title>${escapeXml(guide.h1)}</title>`,
      `      <link>${escapeXml(url)}</link>`,
      `      <guid isPermaLink="true">${escapeXml(url)}</guid>`,
      `      <description>${escapeXml(guide.description)}</description>`,
      `      <pubDate>${rssDate(guide.published)}</pubDate>`,
      ...guide.tags.map((tag) => `      <category>${escapeXml(tag)}</category>`),
      "    </item>",
    ].join("\n");
  });
  const updated = guidesUpdated(guides);
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "  <channel>",
    `    <title>${escapeXml(`${SITE_NAME} guides`)}</title>`,
    `    <link>${escapeXml(absoluteUrl(GUIDES_PATH, origin))}</link>`,
    `    <atom:link href="${escapeXml(absoluteUrl(GUIDES_FEED_PATH, origin))}" rel="self" type="application/rss+xml"/>`,
    "    <description>Practical guides for businesses and creators on Instagram and WhatsApp.</description>",
    "    <language>en</language>",
    ...(updated ? [`    <lastBuildDate>${rssDate(updated)}</lastBuildDate>`] : []),
    ...items,
    "  </channel>",
    "</rss>",
    "",
  ].join("\n");
}
