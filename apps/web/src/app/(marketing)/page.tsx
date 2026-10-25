import "@/components/marketing/effects/effects.css";

import { AutomationShowcase } from "@/components/marketing/AutomationShowcase";
import { MarketingMotion } from "@/components/marketing/effects/MarketingMotion";
import { ScrollReveal } from "@/components/marketing/effects/ScrollReveal";
import { Faq } from "@/components/marketing/Faq";
import { Features } from "@/components/marketing/Features";
import { FinalCta } from "@/components/marketing/FinalCta";
import { Hero } from "@/components/marketing/Hero";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { Integrations } from "@/components/marketing/Integrations";
import { Languages } from "@/components/marketing/Languages";
import { Pricing } from "@/components/marketing/Pricing";
import { SocialProof } from "@/components/marketing/SocialProof";
import { Stats } from "@/components/marketing/Stats";
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

/**
 * The landing page (§3.1 "/"): what the product does, how, on which platforms, and what it costs.
 * Server-rendered; the effects (C-068) are small client islands inside MarketingMotion, and every
 * one of them is still with reduced motion.
 */
export default async function HomePage() {
  const pricing = buildPricing(await fetchPlans());
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(softwareApplicationJsonLd(pricing)) }} />
      <ScrollReveal />
      <MarketingMotion>
        <Hero />
        <Integrations />
        <Features />
        <HowItWorks />
        <AutomationShowcase />
        <Languages />
        <Stats />
        <SocialProof />
        <Pricing pricing={pricing} />
        <Trust />
        <Faq />
        <FinalCta />
      </MarketingMotion>
    </main>
  );
}
