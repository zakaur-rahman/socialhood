import { llmsText } from "@/lib/marketing/llms";

// Built once at build time, like robots.txt and the sitemap.
export const dynamic = "force-static";

/** /llms.txt (llmstxt.org): the product in plain words and links to the public pages (C-142). */
export function GET(): Response {
  return new Response(llmsText(), { headers: { "content-type": "text/markdown; charset=utf-8" } });
}
