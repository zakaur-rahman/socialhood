import "@/components/marketing/effects/effects.css";

import { MarketingMotion } from "@/components/marketing/effects/MarketingMotion";
import { ScrollReveal } from "@/components/marketing/effects/ScrollReveal";
import { FinalCta } from "@/components/marketing/FinalCta";
import { PlanMatrix } from "@/components/marketing/PlanMatrix";
import { Pricing } from "@/components/marketing/Pricing";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { jsonLdString, pageMetadata, softwareApplicationJsonLd } from "@/lib/marketing/seo";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";

// ISR like the landing page: Dodo's prices are read at build and at most once an hour. Segment
// config must be a literal, so this equals PLANS_REVALIDATE_SECONDS.
export const revalidate = 3600;

export const metadata = pageMetadata({
  title: "Pricing",
  description:
    "Amplychat plans: Free to start, Pro with Auto replies, more accounts, team members, WhatsApp broadcasts (coming soon), a product catalogue and the public API. Every limit side by side.",
  path: PRICING_PATH,
});

/** GR-37: the plans with prices from Dodo, then every limit from the API's plan table. */
export default async function PricingPage() {
  const pricing = buildPricing(await fetchPlans());
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(softwareApplicationJsonLd(pricing)) }} />
      <ScrollReveal />
      <MarketingMotion>
        <Pricing pricing={pricing} headingLevel={1} />
        <PlanMatrix />
        <FinalCta />
      </MarketingMotion>
    </main>
  );
}
