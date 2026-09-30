import type { MetadataRoute } from "next";

import { absoluteUrl, siteUrl } from "@/lib/marketing/site";

/**
 * /robots.txt: crawl the public pages, not the signed-in app, sign-in or the digest's unsubscribe
 * links. "/app$" and "/app/" rather than "/app", which would also match /apple-icon.png.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/app$", "/app/", "/w/", "/sign-in", "/unsubscribe"] }],
    sitemap: absoluteUrl("/sitemap.xml", siteUrl()),
  };
}
