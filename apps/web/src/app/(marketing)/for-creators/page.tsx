import { SolutionPageView } from "@/components/marketing/SolutionPageView";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { pageMetadata } from "@/lib/marketing/seo";
import { FOR_CREATORS } from "@/lib/marketing/solutions";

// ISR like the pricing page: Pro's state and price come from the plans API, read at most once an hour.
export const revalidate = 3600;

export const metadata = pageMetadata({ title: FOR_CREATORS.title, description: FOR_CREATORS.description, path: FOR_CREATORS.path });

/** C-156: an audience page, rendered from lib/marketing/solutions.ts. */
export default async function CreatorsPage() {
  const pricing = buildPricing(await fetchPlans());
  return <SolutionPageView page={FOR_CREATORS} pricing={pricing} />;
}
