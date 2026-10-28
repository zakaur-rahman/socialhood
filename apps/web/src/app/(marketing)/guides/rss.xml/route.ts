import { guidesFeed } from "@/lib/marketing/guides/feed";

// Built once at build time, like the sitemap and llms.txt.
export const dynamic = "force-static";

/** /guides/rss.xml: the guides as an RSS 2.0 feed, newest first (C-153). */
export function GET(): Response {
  return new Response(guidesFeed(), { headers: { "content-type": "application/rss+xml; charset=utf-8" } });
}
