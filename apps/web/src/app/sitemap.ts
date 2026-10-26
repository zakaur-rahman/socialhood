import type { MetadataRoute } from "next";

import { LEGAL_DOCUMENTS } from "@/lib/legal";
import { PAGE_UPDATED, PUBLIC_PATHS, absoluteUrl, siteUrl } from "@/lib/marketing/site";

const LAST_MODIFIED: Record<string, string> = {
  ...PAGE_UPDATED,
  ...Object.fromEntries(Object.values(LEGAL_DOCUMENTS).map((document) => [document.path, document.lastUpdated])),
};

/** /sitemap.xml: every public marketing and legal page, at the site URL (NEXT_PUBLIC_SITE_URL). */
export default function sitemap(): MetadataRoute.Sitemap {
  const origin = siteUrl();
  return PUBLIC_PATHS.map((path) => ({
    url: absoluteUrl(path, origin),
    ...(LAST_MODIFIED[path] ? { lastModified: LAST_MODIFIED[path] } : {}),
    changeFrequency: path === "/" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : 0.5,
  }));
}
