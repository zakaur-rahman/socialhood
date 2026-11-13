import { llmsText } from "@/lib/marketing/llms";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { siteUrl } from "@/lib/marketing/site";

// ISR like the pricing page: the plans and their prices come from the plans API (SEO finding 25).
export const revalidate = 3600;

/** /llms.txt (llmstxt.org): the product in plain words, its plans and links to the public pages (C-142). */
export async function GET(): Promise<Response> {
  const pricing = buildPricing(await fetchPlans());
  return new Response(llmsText(siteUrl(), pricing), { headers: { "content-type": "text/markdown; charset=utf-8" } });
}
