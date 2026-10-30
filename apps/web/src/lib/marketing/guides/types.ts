import type { ComponentType } from "react";

import type { SHOTS } from "@/components/marketing/shots";

import { SITE_NAME } from "../site";

/**
 * A guide (C-153): a typed module with its metadata and its body as a React component, rendered by
 * components/marketing/guides/GuideView. No CMS and no MDX: the copy lives in the repo next to the
 * product it describes, so a claim and the code behind it change in the same pull request.
 *
 * Rules for the copy, as on the go-to-market pages (C-122): every product claim is true today, and a
 * feature that waits on Meta's approval or the owner says so; no invented numbers, customers or
 * quotes; competitors only by plain name; sentence case; links to the feature, pricing and compare
 * pages where they help.
 */

/** The topics a guide is filed under; the index shows them on each card. */
export type GuideTag = "Instagram" | "WhatsApp" | "Automations" | "AI replies";

export type GuideFaq = { question: string; answer: string };
/** A link to read next; `lang` when its label is not in English. */
export type GuideLink = { label: string; href: string; lang?: string };

export type Guide = {
  /** The URL segment: /guides/{slug}. Lowercase words and hyphens. */
  slug: string;
  /** For the title tag, at most 48 characters, so "{title} · Amplychat" stays within 60. */
  title: string;
  /** The meta description and the index card's text: 50 to 160 characters. */
  description: string;
  /** The page's one h1; it can be longer than the title. */
  h1: string;
  /** ISO dates (YYYY-MM-DD). Bump `updated` when the copy changes in a way a reader would notice. */
  published: string;
  updated: string;
  /** Minutes at about 200 words a minute; guides.test.ts checks it against the body. */
  readingMinutes: number;
  /** The byline: GUIDE_AUTHOR. */
  author: string;
  tags: GuideTag[];
  /**
   * The body's h2s in order, as written (each body heading is a `GuideH2` with this text). The table
   * of contents reads them; guides.test.tsx checks they match the body.
   */
  sections: readonly string[];
  /** An optional product screenshot under the intro (components/marketing/shots). */
  hero?: keyof typeof SHOTS;
  /** Questions and answers shown at the end of the guide, and emitted as FAQPage. */
  faq?: GuideFaq[];
  /** Two or three pages to read next. */
  related: GuideLink[];
  /** The article body: h2 sections, paragraphs, lists and links, inside the prose styles. */
  Body: ComponentType;
};

/** The byline on every guide. */
export const GUIDE_AUTHOR = `${SITE_NAME} team`;

export const GUIDES_PATH = "/guides";
export const GUIDES_FEED_PATH = "/guides/rss.xml";

/** A section's anchor id from its heading: lowercase words joined by hyphens. */
export function sectionId(heading: string): string {
  return heading
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function guidePath(slug: string): string {
  return `${GUIDES_PATH}/${slug}`;
}
