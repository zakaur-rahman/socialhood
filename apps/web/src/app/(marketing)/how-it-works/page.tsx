import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { HowItWorksStages } from "@/components/marketing/explainers/HowItWorksStages";
import { ExplainerMotion } from "@/components/marketing/explainers/ExplainerMotion";
import { HOW_FAQ, HOW_RELATED, STAGES } from "@/components/marketing/explainers/content";
import { Faq } from "@/components/marketing/Faq";
import { FinalCta } from "@/components/marketing/FinalCta";
import { RelatedCards } from "@/components/marketing/GtmPageView";
import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { INTEGRATIONS } from "@/components/marketing/landing/Channels";
import { Ico } from "@/components/marketing/landing/Ico";
import { CtaLink } from "@/components/marketing/primitives";
import { buildPricing, fetchPlans } from "@/lib/marketing/plans";
import { pageMetadata } from "@/lib/marketing/seo";
import { FEATURES_PATH, HOW_IT_WORKS_PATH, SIGN_UP_PATH, SITE_NAME, appUrl } from "@/lib/marketing/site";

// ISR like the landing page: the closing band's trial line follows Pro's state in the plans API.
export const revalidate = 3600;

export const metadata = pageMetadata({
  title: `How ${SITE_NAME} works`,
  description:
    "From connecting Instagram, WhatsApp and website chat to AI replies from your own knowledge, hand-offs, automations and a weekly report, step by step.",
  path: HOW_IT_WORKS_PATH,
});

/** The three channels the head shows flowing into the inbox (the landing's connection rows). */
const CHANNELS = ["Instagram", "WhatsApp", "Website chat"].map((name) => INTEGRATIONS.find((item) => item.name === name)!);

/**
 * /how-it-works (C-160): the product as a guided flow. A page head, then the eight stages as one
 * ordered list down a line that draws as you scroll (CSS scroll timeline, a static line elsewhere),
 * with a sticky step tracker on a wide screen; each stage a short explanation beside a product scene
 * (the landing's own scenes where they fit). Then a few common questions, related pages and the
 * closing band. Server-rendered; one idle island (ExplainerMotion) marks the current stage and plays
 * each scene once as it arrives.
 */
export default async function HowItWorksPage() {
  const pricing = buildPricing(await fetchPlans());
  const pro = pricing.plans.find((card) => card.plan === "pro");
  return (
    <main id="main" tabIndex={-1} className="pp xp flex-1 outline-none">
      <BreadcrumbJsonLd name="How it works" path={HOW_IT_WORKS_PATH} />
      <section className="page-head pp-head xp-head" aria-labelledby="how-title">
        <div className="wrap pp-head-grid">
          <div>
            <p className="kicker">How it works</p>
            <h1 id="how-title" className="h-page">
              From first message to reply
            </h1>
            <p className="lede">
              Connect your accounts, add what your business knows, and every message lands in one inbox where the AI drafts or
              sends the reply and hands the tricky ones to you.
            </p>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={FEATURES_PATH} variant="secondary">
                See every feature
              </CtaLink>
            </div>
          </div>
          {/* At a glance: three channels into one inbox, then the AI. A picture of the flow below. */}
          <figure className="xp-glance" data-ui="" aria-label="Instagram, WhatsApp and website chat flow into one inbox, where the AI drafts the reply.">
            <ul className="xp-glance-in">
              {CHANNELS.map((item) => (
                <li key={item.name}>
                  <Ico className="ico-mark" style={{ "--c": item.mark } as CSSProperties}>
                    <PlatformGlyph platform={item.platform!} />
                  </Ico>
                  {item.name}
                </li>
              ))}
            </ul>
            <span className="xp-glance-join" aria-hidden />
            <p className="xp-glance-box">
              <b>One inbox</b>
              <span className="tag t-draft">AI draft</span>
              <span className="tag t-need">Needs you</span>
            </p>
            <p className="xp-glance-foot">
              <Check className="size-4" strokeWidth={2.4} aria-hidden />
              {STAGES.length} steps, from connecting to seeing what works
            </p>
          </figure>
        </div>
      </section>

      <HowItWorksStages />

      <Faq items={HOW_FAQ} id="questions" allLink lede="Short answers about the AI, the accounts and the rules." />
      <RelatedCards links={HOW_RELATED} />
      <FinalCta trialDays={pro?.available ? pro.trialDays : 0} from="how-it-works" />
      <ExplainerMotion scenes />
    </main>
  );
}
