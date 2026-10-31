import { ArrowRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { BentoGrid } from "@/components/marketing/explainers/BentoGrid";
import { ExplainerMotion } from "@/components/marketing/explainers/ExplainerMotion";
import { FeatureDetails } from "@/components/marketing/explainers/FeatureDetails";
import { FinalCta } from "@/components/marketing/FinalCta";
import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { CtaLink } from "@/components/marketing/primitives";
import { COMPARE_PATH } from "@/lib/marketing/gtm-pages";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { pageMetadata } from "@/lib/marketing/seo";
import { FEATURES_PATH, HOW_IT_WORKS_PATH, SIGN_UP_PATH, SITE_NAME, appUrl } from "@/lib/marketing/site";

// ISR like the pricing page: Pro's state (and the closing band's trial line) come from the plans API.
export const revalidate = 3600;

export const metadata = pageMetadata({
  title: `${SITE_NAME} features`,
  description:
    "The AI inbox for Instagram, WhatsApp and website chat, AI replies from your knowledge, comment-to-DM, scheduling and analytics, with each plan's limits.",
  path: FEATURES_PATH,
});

/** A few comparisons to start from; the hub has them all. */
const COMPARE_LINKS = [
  { label: `${SITE_NAME} vs Manychat`, href: "/compare/manychat" },
  { label: `${SITE_NAME} vs Interakt`, href: "/compare/interakt" },
  { label: "Switch from Manychat", href: "/switch-from-manychat" },
  { label: "All comparisons", href: COMPARE_PATH },
];

/**
 * /features (C-160): every feature on one page. A page head, a bento grid (the three headline
 * features large with a small product scene each, the rest in medium and small cells, each with its
 * icon, a line, a status chip where it isn't live, and a link to its own page or its details), then
 * "In detail" (each group with a fuller explanation, the specifics and its limits on each plan, beside
 * a sticky side nav), a comparison teaser and the closing band. Server-rendered; one idle island.
 */
export default async function FeaturesPage() {
  const pricing = buildPricing(await fetchPlans());
  const pro = pricing.plans.find((card) => card.plan === "pro");
  return (
    <main id="main" tabIndex={-1} className="pp xp flex-1 outline-none">
      <BreadcrumbJsonLd name="Features" path={FEATURES_PATH} />
      <section className="page-head pp-head xp-head" aria-labelledby="features-title">
        <div className="wrap xp-head-split">
          <div>
            <p className="kicker">Features</p>
            <h1 id="features-title" className="h-page">
              Everything your customer conversations need
            </h1>
          </div>
          <div>
            <p className="lede">
              From the first comment to the reply that closes the sale, in one place. Each feature says what runs today and what
              each plan includes.
            </p>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={HOW_IT_WORKS_PATH} variant="secondary">
                See how it works
              </CtaLink>
            </div>
          </div>
        </div>
      </section>

      <BentoGrid />
      <FeatureDetails pricing={pricing} />

      <section className="band xp-compare" aria-labelledby="compare-title">
        <div className="wrap xp-compare-in">
          <div>
            <h2 id="compare-title" className="h-sec">
              How {SITE_NAME} compares
            </h2>
            <p className="lede">
              Side by side with Instagram DM tools and WhatsApp platforms, from each vendor&apos;s own dated pages, with our side
              checked against our code.
            </p>
          </div>
          <ul className="rcards">
            {COMPARE_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href as Route} className="rcard">
                  <span>{link.label}</span>
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <FinalCta trialDays={pro?.available ? pro.trialDays : 0} />
      <ExplainerMotion />
    </main>
  );
}
