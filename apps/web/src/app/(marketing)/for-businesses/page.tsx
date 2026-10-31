import { SolutionPageView } from "@/components/marketing/SolutionPageView";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { pageMetadata } from "@/lib/marketing/seo";
import { FOR_BUSINESSES } from "@/lib/marketing/solutions";

// ISR like the pricing page: Pro's state and price come from the plans API, read at most once an hour.
export const revalidate = 3600;

export const metadata = pageMetadata({ title: FOR_BUSINESSES.title, description: FOR_BUSINESSES.description, path: FOR_BUSINESSES.path });

/** C-156: an audience page, rendered from lib/marketing/solutions.ts. */
export default async function BusinessesPage() {
  const pricing = buildPricing(await fetchPlans());
  return <SolutionPageView page={FOR_BUSINESSES} pricing={pricing} />;
}
