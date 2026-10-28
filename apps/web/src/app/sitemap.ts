import type { MetadataRoute } from "next";

import { LEGAL_DOCUMENTS } from "@/lib/legal";
import { GUIDES, GUIDES_PATH, guidePath, guidesUpdated } from "@/lib/marketing/guides";
import { LANDING_LANGUAGES } from "@/lib/marketing/seo";
import { PAGE_UPDATED, PUBLIC_PATHS, absoluteUrl, siteUrl } from "@/lib/marketing/site";

const LAST_MODIFIED: Record<string, string> = {
  ...PAGE_UPDATED,
  ...Object.fromEntries(Object.values(LEGAL_DOCUMENTS).map((document) => [document.path, document.lastUpdated])),
  [GUIDES_PATH]: guidesUpdated(),
  ...Object.fromEntries(GUIDES.map((guide) => [guidePath(guide.slug), guide.updated])),
};

/** The landing page and its Hinglish version list each other as hreflang alternates (C-153). */
const LANGUAGE_PATHS = new Set<string>(Object.values(LANDING_LANGUAGES));

/**
 * /sitemap.xml: every public marketing and legal page, then each guide (C-153), at the site URL
 * (NEXT_PUBLIC_SITE_URL). Dates are when the content changed, never the build time.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const origin = siteUrl();
  const languages = Object.fromEntries(Object.entries(LANDING_LANGUAGES).map(([code, path]) => [code, absoluteUrl(path, origin)]));
  return [...PUBLIC_PATHS, ...GUIDES.map((guide) => guidePath(guide.slug))].map((path) => ({
    url: absoluteUrl(path, origin),
    ...(LAST_MODIFIED[path] ? { lastModified: LAST_MODIFIED[path] } : {}),
    changeFrequency: path === "/" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : 0.5,
    ...(LANGUAGE_PATHS.has(path) ? { alternates: { languages } } : {}),
  }));
}
