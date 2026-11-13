import { FinalCta } from "@/components/marketing/FinalCta";
import { BreadcrumbJsonLd, JsonLd } from "@/components/marketing/JsonLd";
import { PlanMatrix } from "@/components/marketing/PlanMatrix";
import { Pricing } from "@/components/marketing/Pricing";
import { WhatsAppCharges } from "@/components/marketing/WhatsAppCharges";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { DESCRIPTION_MAX, TITLE_MAX, pageMetadata, softwareApplicationJsonLd } from "@/lib/marketing/seo";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";

// ISR like the landing page: the plans and Dodo's prices are read at build and at most every five
// minutes (C-173), so a release that changes plans doesn't show stale limits for an hour. Segment
// config must be a literal, so this equals PLANS_REVALIDATE_SECONDS.
export const revalidate = 300;

/**
 * SEO finding 8: the title and description name the monthly prices, read from the same plan list as
 * the page (never typed in). Unless both Creator and Business are on sale with a price, or when the text
 * would run past what search results show, they name the plans without prices.
 */
export async function generateMetadata() {
  const pricing = buildPricing(await fetchPlans());
  const price = (plan: string) => pricing.plans.find((card) => card.plan === plan && card.available)?.price;
  const [creator, business] = [price("pro"), price("max")];
  const priced = creator && business;
  const title = priced ? `Amplychat pricing: Free, Creator ${creator}, Business ${business} a month` : "";
  const description = priced
    ? `Amplychat plans side by side: Free to start, Creator at ${creator} and Business at ${business} a month with Auto replies, more channels and team members, and every limit.`
    : "";
  return pageMetadata({
    title: title && title.length <= TITLE_MAX ? title : "Amplychat pricing: Free, Creator and Business plans",
    description:
      description && description.length <= DESCRIPTION_MAX
        ? description
        : "Amplychat plans side by side: Free to start, Creator and Business with Auto replies, more channels and team members, and every limit of each plan.",
    path: PRICING_PATH,
  });
}

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
