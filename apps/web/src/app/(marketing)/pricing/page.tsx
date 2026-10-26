import "@/components/marketing/effects/effects.css";

import { MarketingMotion } from "@/components/marketing/effects/MarketingMotion";
import { ScrollReveal } from "@/components/marketing/effects/ScrollReveal";
import { FinalCta } from "@/components/marketing/FinalCta";
import { BreadcrumbJsonLd, JsonLd } from "@/components/marketing/JsonLd";
import { PlanMatrix } from "@/components/marketing/PlanMatrix";
import { Pricing } from "@/components/marketing/Pricing";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { pageMetadata, softwareApplicationJsonLd } from "@/lib/marketing/seo";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";

// ISR like the landing page: Dodo's prices are read at build and at most once an hour. Segment
// config must be a literal, so this equals PLANS_REVALIDATE_SECONDS.
export const revalidate = 3600;

export const metadata = pageMetadata({
  title: "Pricing",
  description:
    "Amplychat plans side by side: Free to start, Pro with Auto replies, more accounts and team members, and every limit of each plan.",
  path: PRICING_PATH,
});

/** GR-37: the plans with prices from Dodo, then every limit from the API's plan table. */
export default async function PricingPage() {
  const pricing = buildPricing(await fetchPlans());
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <JsonLd data={softwareApplicationJsonLd(pricing)} />
      <BreadcrumbJsonLd name="Pricing" path={PRICING_PATH} />
      <ScrollReveal />
      <MarketingMotion>
        <Pricing pricing={pricing} headingLevel={1} />
        <PlanMatrix />
        <FinalCta />
      </MarketingMotion>
    </main>
  );
}
