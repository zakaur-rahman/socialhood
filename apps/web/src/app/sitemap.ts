import type { MetadataRoute } from "next";

import { LEGAL_DOCUMENTS } from "@/lib/legal";
import { CHANGELOG_PATH, changelogUpdated } from "@/lib/marketing/changelog";
import { GLOSSARY, glossaryPath } from "@/lib/marketing/glossary";
import { GUIDES, GUIDES_PATH, guidePath, guidesUpdated } from "@/lib/marketing/guides";
import { PAGE_UPDATED, PUBLIC_PATHS, absoluteUrl, siteUrl } from "@/lib/marketing/site";

const LAST_MODIFIED: Record<string, string> = {
  ...PAGE_UPDATED,
  ...Object.fromEntries(Object.values(LEGAL_DOCUMENTS).map((document) => [document.path, document.lastUpdated])),
  [GUIDES_PATH]: guidesUpdated(),
  // C-156: What's new changes when an entry is added.
  [CHANGELOG_PATH]: changelogUpdated(),
  ...Object.fromEntries(GUIDES.map((guide) => [guidePath(guide.slug), guide.updated])),
  // C-163 (gloss): each glossary term its own date.
  ...Object.fromEntries(GLOSSARY.map((term) => [glossaryPath(term.slug), term.updated])),
};

/**
 * /sitemap.xml: every public marketing and legal page, then each guide (C-153), at the site URL
 * (NEXT_PUBLIC_SITE_URL). Dates are when the content changed, never the build time.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const origin = siteUrl();
  return [...PUBLIC_PATHS, ...GUIDES.map((guide) => guidePath(guide.slug)), ...GLOSSARY.map((term) => glossaryPath(term.slug))].map((path) => ({
    url: absoluteUrl(path, origin),
    ...(LAST_MODIFIED[path] ? { lastModified: LAST_MODIFIED[path] } : {}),
    changeFrequency: path === "/" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : 0.5,
  }));
}
