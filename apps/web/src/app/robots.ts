import type { MetadataRoute } from "next";

import { ROBOTS_DISALLOW, absoluteUrl, siteUrl } from "@/lib/marketing/site";

/** /robots.txt: crawl the public pages, find them all in the sitemap, keep out of the private ones. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: [...ROBOTS_DISALLOW] }],
    sitemap: absoluteUrl("/sitemap.xml", siteUrl()),
  };
}
