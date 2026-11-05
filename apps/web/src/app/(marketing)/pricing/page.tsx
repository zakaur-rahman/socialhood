import { FinalCta } from "@/components/marketing/FinalCta";
import { BreadcrumbJsonLd, JsonLd } from "@/components/marketing/JsonLd";
import { PlanMatrix } from "@/components/marketing/PlanMatrix";
import { Pricing } from "@/components/marketing/Pricing";
import { WhatsAppCharges } from "@/components/marketing/WhatsAppCharges";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { pageMetadata, softwareApplicationJsonLd } from "@/lib/marketing/seo";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";

// ISR like the landing page: the plans and Dodo's prices are read at build and at most every five
// minutes (C-173), so a release that changes plans doesn't show stale limits for an hour. Segment
// config must be a literal, so this equals PLANS_REVALIDATE_SECONDS.
export const revalidate = 300;

export const metadata = pageMetadata({
  title: "Pricing",
  description:
    "Amplychat plans side by side: Free to start, Creator and Business with Auto replies, more channels and team members, and every limit of each plan.",
  path: PRICING_PATH,
});

/** GR-37: the plans with prices from Dodo, every limit from the API's plan table (C-155 look), then Meta's WhatsApp charges (C-156). */
export default async function PricingPage() {
  const pricing = buildPricing(await fetchPlans());
  const pro = pricing.plans.find((card) => card.plan === "pro");
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <JsonLd data={softwareApplicationJsonLd(pricing)} />
      <BreadcrumbJsonLd name="Pricing" path={PRICING_PATH} />
      <Pricing pricing={pricing} />
      <PlanMatrix />
      <WhatsAppCharges />
      <FinalCta trialDays={pro?.available ? pro.trialDays : 0} />
    </main>
  );
}
