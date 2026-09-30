import type { MetadataRoute } from "next";

import { LEGAL_DOCUMENTS } from "@/lib/legal";
import { PUBLIC_PATHS, absoluteUrl, siteUrl } from "@/lib/marketing/site";

const LAST_UPDATED: Record<string, string> = Object.fromEntries(
  Object.values(LEGAL_DOCUMENTS).map((document) => [document.path, document.lastUpdated]),
);

/** /sitemap.xml: the public marketing and legal pages, at the site URL (NEXT_PUBLIC_SITE_URL). */
export default function sitemap(): MetadataRoute.Sitemap {
  const origin = siteUrl();
  return PUBLIC_PATHS.map((path) => ({
    url: absoluteUrl(path, origin),
    ...(LAST_UPDATED[path] ? { lastModified: LAST_UPDATED[path] } : {}),
    changeFrequency: path === "/" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : 0.5,
  }));
}
