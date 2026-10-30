import { Faq } from "@/components/marketing/Faq";
import { FinalCta } from "@/components/marketing/FinalCta";
import { JsonLd } from "@/components/marketing/JsonLd";
import { Audience } from "@/components/marketing/landing/Audience";
import { Comments } from "@/components/marketing/landing/Comments";
import { Decide } from "@/components/marketing/landing/Decide";
import { Features } from "@/components/marketing/landing/Features";
import { Hero } from "@/components/marketing/landing/Hero";
import { LandingMotion } from "@/components/marketing/landing/LandingMotion";
import { Modes } from "@/components/marketing/landing/Modes";
import { Steps } from "@/components/marketing/landing/Steps";
import { Trust } from "@/components/marketing/landing/Trust";
import { Pricing } from "@/components/marketing/Pricing";
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
 * The landing page (§3.1 "/", C-155; order C-157): the owner's design, paper bands with a night band
 * every two or three sections, with the site's own words: the hero and its facts, How it works (night,
 * the peak), Automations, Modes, Security (night), Who it's for, Features with the connections, the
 * setup steps (night) into Pricing, the FAQ and the closer (night). Every section is server-rendered and meaningful without script; one small
 * island (LandingMotion) brings the scenes to life after load, and leaves them still under reduced
 * motion. The pricing cards and the trial perk come from the plans API.
 */
export default async function HomePage() {
  const pricing = buildPricing(await fetchPlans());
  const pro = pricing.plans.find((card) => card.plan === "pro");
  return (
    <main id="main" tabIndex={-1} data-landing="" className="flex-1 outline-none">
      <JsonLd data={landingJsonLd(pricing, FAQ)} />
      <Hero />
      <Decide />
      <Comments />
      <Modes />
      <Trust />
      <Audience />
      <Features />
      <Steps />
      <Pricing pricing={pricing} />
      <Faq />
      <FinalCta trialDays={pro?.available ? pro.trialDays : 0} />
      <LandingMotion />
    </main>
  );
}
