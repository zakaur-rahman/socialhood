import { Faq } from "@/components/marketing/Faq";
import { Features } from "@/components/marketing/Features";
import { FinalCta } from "@/components/marketing/FinalCta";
import { Hero } from "@/components/marketing/Hero";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { Platforms } from "@/components/marketing/Platforms";
import { Pricing } from "@/components/marketing/Pricing";
import { Trust } from "@/components/marketing/Trust";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { jsonLdString, pageMetadata, softwareApplicationJsonLd } from "@/lib/marketing/seo";
import { SITE_DESCRIPTION, SITE_NAME, SITE_TAGLINE } from "@/lib/marketing/site";

// ISR: the plan list (prices from Dodo) is read at build and again at most once an hour.
export const revalidate = 3600;

export const metadata = pageMetadata({
  title: `${SITE_NAME} · ${SITE_TAGLINE}`,
  description: SITE_DESCRIPTION,
  path: "/",
  absoluteTitle: true,
});

/** The landing page (§3.1 "/"): what Social Hood does, how, on which platforms, and what it costs. */
export default async function HomePage() {
  const pricing = buildPricing(await fetchPlans());
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(softwareApplicationJsonLd(pricing)) }} />
      <Hero />
      <Features />
      <HowItWorks />
      <Platforms />
      <Trust />
      <Pricing pricing={pricing} />
      <Faq />
      <FinalCta />
    </main>
  );
}
