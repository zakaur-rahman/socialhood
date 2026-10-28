import "@/components/marketing/effects/effects.css";

import { Suspense } from "react";

import { AutomationShowcase } from "@/components/marketing/AutomationShowcase";
import { MarketingMotion } from "@/components/marketing/effects/MarketingMotion";
import { ScrollReveal } from "@/components/marketing/effects/ScrollReveal";
import { Faq } from "@/components/marketing/Faq";
import { Features } from "@/components/marketing/Features";
import { FinalCta } from "@/components/marketing/FinalCta";
import { Hero } from "@/components/marketing/Hero";
import { JsonLd } from "@/components/marketing/JsonLd";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { Integrations } from "@/components/marketing/Integrations";
import { Languages } from "@/components/marketing/Languages";
import { Pricing } from "@/components/marketing/Pricing";
import { ProductShot } from "@/components/marketing/ProductShot";
import { SocialProof } from "@/components/marketing/SocialProof";
import { Stats } from "@/components/marketing/Stats";
import { Trust } from "@/components/marketing/Trust";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { FAQ } from "@/lib/marketing/faq";
import { landingJsonLd, pageMetadata } from "@/lib/marketing/seo";
import { SITE_DESCRIPTION, SITE_NAME, SITE_TITLE_LINE } from "@/lib/marketing/site";

// ISR: the plan list (prices from Dodo) is read at build and again at most once an hour.
export const revalidate = 3600;

export const metadata = pageMetadata({
  title: `${SITE_NAME} · ${SITE_TITLE_LINE}`,
  description: SITE_DESCRIPTION,
  path: "/",
  absoluteTitle: true,
});

/**
 * The landing page (§3.1 "/"): what the product does, how, on which platforms, and what it costs.
 * Server-rendered; the effects (C-068) are small client islands inside MarketingMotion, and every
 * one of them is still with reduced motion. Each section after the hero sits in its own Suspense
 * boundary, which adds only comment markers to the HTML but lets React hydrate a section at a time,
 * yielding to the browser in between, instead of in one long task (C-152).
 */
export default async function HomePage() {
  const pricing = buildPricing(await fetchPlans());
  return (
    <main id="main" tabIndex={-1} data-landing="" className="flex-1 outline-none">
      <JsonLd data={landingJsonLd(pricing, FAQ)} />
      <ScrollReveal />
      <MarketingMotion>
        <Hero />
        <Suspense>
          <ProductShot />
        </Suspense>
        <Suspense>
          <Integrations />
        </Suspense>
        <Suspense>
          <Features />
        </Suspense>
        <Suspense>
          <HowItWorks />
        </Suspense>
        <Suspense>
          <AutomationShowcase />
        </Suspense>
        <Suspense>
          <Languages />
        </Suspense>
        <Suspense>
          <Stats />
        </Suspense>
        <Suspense>
          <SocialProof />
        </Suspense>
        <Suspense>
          <Pricing pricing={pricing} />
        </Suspense>
        <Suspense>
          <Trust />
        </Suspense>
        <Suspense>
          <Faq />
        </Suspense>
        <Suspense>
          <FinalCta />
        </Suspense>
      </MarketingMotion>
    </main>
  );
}
