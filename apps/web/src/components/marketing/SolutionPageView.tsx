import { ArrowRight, Check, Clock } from "lucide-react";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { StatusChip } from "@/components/site/StatusChip";
import type { PlanCard, Pricing } from "@/lib/marketing/plans";
import { FAQ_ALL } from "@/lib/marketing/faq";
import { faqPageJsonLd, uniqueFaq } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, SITE_NAME, absoluteUrl, appUrl, siteUrl } from "@/lib/marketing/site";
import type { SolutionPage, Tier } from "@/lib/marketing/solutions";
import { cn } from "@/lib/utils";

import { Faq } from "./Faq";
import { FinalCta } from "./FinalCta";
import { RelatedCards } from "./GtmPageView";
import { BreadcrumbJsonLd, JsonLd } from "./JsonLd";
import { INTEGRATIONS } from "./landing/Channels";
import { Ico } from "./landing/Ico";
import { AI_TITLES, cardIcon } from "./page-icons";
import { CtaLink, SECTION_EYEBROW } from "./primitives";

const DOT = { live: "var(--ok)", waiting: "var(--wait-mark)", yours: "var(--iris)" } as const;

/** What a plan says today: Free is available; Pro's state and price come only from the plans API. */
function planState(card: PlanCard | undefined): { label: string; tone: "t-ok" | "t-plain" | "t-draft" } {
  if (!card) return { label: "Coming soon", tone: "t-plain" };
  if (card.plan === "free") return { label: "Available now", tone: "t-ok" };
  if (!card.available) return { label: "Coming soon", tone: "t-plain" };
  return { label: card.price ? `${card.price} a month` : "Price shown at sign-up", tone: "t-draft" };
}

/** A tier on the landing's plan-card skin (C-159): a sheet, the name, who it's for, the plan and its state. */
function TierCard({ tier, pricing }: { tier: Tier; pricing: Pricing }) {
  const card = pricing.plans.find((plan) => plan.plan === tier.plan);
  const state = planState(card);
  const id = `tier-${tier.name.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <li className="tier" aria-labelledby={id}>
      <h3 id={id}>{tier.name}</h3>
      <p className="for">{tier.who}</p>
      <p className="tier-plan">
        {card?.name ?? tier.plan}
        <span className={cn("tag", state.tone)}>{state.label}</span>
      </p>
      <p className="tier-b">{tier.body}</p>
    </li>
  );
}

/**
 * /for-creators and /for-businesses (C-156; C-159 look): the head beside an "at a glance" card,
 * "Sounds familiar?" as before and after cards, the features as icon cards with their status, the
 * integrations (businesses), plans by audience size on the plan-card skin (no testimonials: there
 * are none to show), the FAQ (its FAQPage JSON-LD names only the questions /faq doesn't already mark
 * up, C-162), related pages and the night closing band.
 * The content is lib/marketing/solutions.ts; Pro's state comes from the plans API.
 */
export function SolutionPageView({ page, pricing }: { page: SolutionPage; pricing: Pricing }) {
  const origin = siteUrl();
  const pro = pricing.plans.find((card) => card.plan === "pro");
  const ownFaq = uniqueFaq(page.faq, FAQ_ALL);
  return (
    <main id="main" tabIndex={-1} className="pp flex-1 outline-none">
      <BreadcrumbJsonLd name={page.name} path={page.path} />
      {ownFaq.length ? (
        <JsonLd data={{ "@context": "https://schema.org", ...faqPageJsonLd(ownFaq, origin, `${absoluteUrl(page.path, origin)}#faq`) }} />
      ) : null}
      <section className="page-head pp-head">
        <div className="wrap pp-head-grid">
          <div>
            <p className={SECTION_EYEBROW}>{page.eyebrow}</p>
            <h1 className="h-page">{page.h1}</h1>
            <p className="lede">{page.intro}</p>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href="/pricing" variant="secondary">
                See plans and limits
              </CtaLink>
            </div>
          </div>
          <div className="pp-toc glance">
            <p className="pp-toc-h">{page.featuresTitle}</p>
            <ul>
              {page.features.map((feature) => (
                <li key={feature.title}>
                  <span>{feature.title}</span>
                  {feature.status && feature.status !== "yes" ? <StatusChip status={feature.status} /> : null}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section aria-labelledby="familiar-title" className="band">
        <div className="wrap">
          <h2 id="familiar-title" className="h-sec">
            Sounds familiar?
          </h2>
          <ul className="ba after-head">
            {page.familiar.map((item) => (
              <li key={item.before} className="ba-card">
                <div className="ba-before">
                  <p className="ba-h">
                    <Clock size={16} strokeWidth={1.75} aria-hidden />
                    Before
                  </p>
                  <p>{item.before}</p>
                </div>
                <div className="ba-after">
                  <p className="ba-h">
                    <Check size={16} strokeWidth={2.25} aria-hidden />
                    With {SITE_NAME}
                  </p>
                  <p>{item.after}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="features-title" className="band">
        <div className="wrap">
          <div className="split-head">
            <h2 id="features-title" className="h-sec">
              {page.featuresTitle}
            </h2>
            <p className="lede">{page.featuresIntro}</p>
          </div>
          <ul className="gcards after-head">
            {page.features.map((feature) => (
              <li key={feature.title} className="gcard">
                <Ico icon={cardIcon(feature.title)} className={AI_TITLES.has(feature.title) ? "ico-ai" : undefined} />
                <h3>
                  {feature.title}
                  {feature.status && feature.status !== "yes" ? <StatusChip status={feature.status} /> : null}
                </h3>
                <p>{feature.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {page.integrations ? (
        <section aria-labelledby="integrations-title" className="band">
          <div className="wrap">
            <div className="split-head">
              <h2 id="integrations-title" className="h-sec">
                Integrations, and what runs today
              </h2>
              <p className="lede">
                Instagram and WhatsApp connect only through Meta&apos;s official APIs, and we never ask for your password.
              </p>
            </div>
            <ul className="gcards is-3 after-head">
              {INTEGRATIONS.map((item) => (
                <li key={item.name} className="gcard">
                  {item.platform ? (
                    <Ico className="ico-mark" style={{ "--c": item.mark } as CSSProperties}>
                      <PlatformGlyph platform={item.platform} />
                    </Ico>
                  ) : (
                    <Ico icon={item.icon} />
                  )}
                  <h3>{item.name}</h3>
                  <p>{item.body}</p>
                  <span className="st" style={{ "--sc": DOT[item.tone] } as CSSProperties}>
                    {item.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      <section aria-labelledby="tiers-title" className="band">
        <div className="wrap">
          <div className="split-head">
            <h2 id="tiers-title" className="h-sec">
              Which plan fits
            </h2>
            <p className="lede">{page.tiersIntro}</p>
          </div>
          <ul className="tiers after-head">
            {page.tiers.map((tier) => (
              <TierCard key={tier.name} tier={tier} pricing={pricing} />
            ))}
          </ul>
        </div>
      </section>

      <Faq items={page.faq} eyebrow="FAQ" lede="Short answers about safety, the AI and the plans." />

      <RelatedCards links={page.related} />
      <FinalCta trialDays={pro?.available ? pro.trialDays : 0} />
    </main>
  );
}
