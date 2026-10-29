import { ArrowRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { STATUS_LABEL } from "@/lib/marketing/gtm-pages";
import type { PlanCard, Pricing } from "@/lib/marketing/plans";
import { faqPageJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, SITE_NAME, absoluteUrl, appUrl, siteUrl } from "@/lib/marketing/site";
import type { SolutionPage, Tier } from "@/lib/marketing/solutions";
import { cn } from "@/lib/utils";

import { Faq } from "./Faq";
import { BreadcrumbJsonLd, JsonLd } from "./JsonLd";
import { INTEGRATIONS } from "./landing/Channels";
import { Container, CtaLink, SECTION_EYEBROW } from "./primitives";

const LINK = "font-medium text-brand-fg underline-offset-4 hover:underline";
const DOT = { live: "var(--ok)", waiting: "var(--wait-mark)", yours: "var(--iris)" } as const;

/** What a plan says today: Free is available; Pro's state and price come only from the plans API. */
function planState(card: PlanCard | undefined): { label: string; tone: "t-ok" | "t-plain" | "t-draft" } {
  if (!card) return { label: "Coming soon", tone: "t-plain" };
  if (card.plan === "free") return { label: "Available now", tone: "t-ok" };
  if (!card.available) return { label: "Coming soon", tone: "t-plain" };
  return { label: card.price ? `${card.price} a month` : "Price shown at sign-up", tone: "t-draft" };
}

function TierCard({ tier, pricing }: { tier: Tier; pricing: Pricing }) {
  const card = pricing.plans.find((plan) => plan.plan === tier.plan);
  const state = planState(card);
  const id = `tier-${tier.name.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <li className="card flex flex-col p-6" aria-labelledby={id}>
      <h3 id={id} className="text-lg font-semibold">
        {tier.name}
      </h3>
      <p className="mt-1 text-sm text-fg-secondary">{tier.who}</p>
      <p className="mt-5 flex flex-wrap items-center gap-2 text-sm font-semibold">
        {card?.name ?? tier.plan}
        <span className={cn("tag", state.tone)}>{state.label}</span>
      </p>
      <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{tier.body}</p>
    </li>
  );
}

/**
 * /for-creators and /for-businesses (C-156): the hero with one h1, "Sounds familiar?" before and
 * after, the features with their status, the integrations (businesses), plans by audience size
 * (no testimonials: there are none to show), the FAQ with its FAQPage JSON-LD, and related pages.
 * The content is lib/marketing/solutions.ts; Pro's state comes from the plans API.
 */
export function SolutionPageView({ page, pricing }: { page: SolutionPage; pricing: Pricing }) {
  const origin = siteUrl();
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <BreadcrumbJsonLd name={page.name} path={page.path} />
      <JsonLd data={{ "@context": "https://schema.org", ...faqPageJsonLd(page.faq, origin, `${absoluteUrl(page.path, origin)}#faq`) }} />
      <section className="page-head">
        <Container className="max-w-3xl">
          <p className={SECTION_EYEBROW}>{page.eyebrow}</p>
          <h1 className="h-page">{page.h1}</h1>
          <p className="lede">{page.intro}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="w-full px-6 sm:w-auto">
              Start free <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <CtaLink href="/pricing" variant="secondary" className="w-full px-6 sm:w-auto">
              See plans and limits
            </CtaLink>
          </div>
        </Container>
      </section>

      <section aria-labelledby="familiar-title" className="band">
        <Container>
          <h2 id="familiar-title" className="h-sec">
            Sounds familiar?
          </h2>
          <ul className="mt-8 grid gap-4 md:grid-cols-2">
            {page.familiar.map((item) => (
              <li key={item.before} className="card p-5">
                <p className="text-sm leading-relaxed text-fg-secondary">
                  <span className="mb-1 block text-xs font-semibold text-fg">Before</span>
                  {item.before}
                </p>
                <p className="mt-4 text-sm leading-relaxed text-fg">
                  <span className="mb-1 block text-xs font-semibold text-brand-fg">With {SITE_NAME}</span>
                  {item.after}
                </p>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      <section aria-labelledby="features-title" className="band">
        <Container>
          <h2 id="features-title" className="h-sec">
            {page.featuresTitle}
          </h2>
          <p className="mt-3 max-w-2xl text-base text-fg-secondary">{page.featuresIntro}</p>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2">
            {page.features.map((feature) => (
              <li key={feature.title} className="card p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold">{feature.title}</h3>
                  {feature.status && feature.status !== "yes" ? (
                    <span className="tag t-need">{STATUS_LABEL[feature.status]}</span>
                  ) : null}
                </div>
                <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{feature.body}</p>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      {page.integrations ? (
        <section aria-labelledby="integrations-title" className="band">
          <Container>
            <h2 id="integrations-title" className="h-sec">
              Integrations, and what runs today
            </h2>
            <p className="mt-3 max-w-2xl text-base text-fg-secondary">
              Instagram and WhatsApp connect only through Meta&apos;s official APIs, and we never ask for your password.
            </p>
            <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {INTEGRATIONS.map((item) => (
                <li key={item.name} className="card p-5">
                  <h3 className="text-base font-semibold">{item.name}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{item.body}</p>
                  <p className="mt-3 inline-flex items-center gap-2 text-xs font-semibold">
                    <i aria-hidden className="inline-block size-2 rounded-full" style={{ background: DOT[item.tone] }} />
                    {item.status}
                  </p>
                </li>
              ))}
            </ul>
          </Container>
        </section>
      ) : null}

      <section aria-labelledby="tiers-title" className="band">
        <Container>
          <h2 id="tiers-title" className="h-sec">
            Which plan fits
          </h2>
          <p className="mt-3 max-w-2xl text-base text-fg-secondary">{page.tiersIntro}</p>
          <ul className="mt-8 grid gap-4 md:grid-cols-3">
            {page.tiers.map((tier) => (
              <TierCard key={tier.name} tier={tier} pricing={pricing} />
            ))}
          </ul>
        </Container>
      </section>

      <Faq items={page.faq} eyebrow="FAQ" lede="Short answers about safety, the AI and the plans." />

      <section aria-labelledby="related-title" className="band">
        <Container className="max-w-3xl">
          <h2 id="related-title" className="h-sec">
            Keep reading
          </h2>
          <ul className="mt-5 grid gap-1 text-sm">
            {page.related.map((link) => (
              <li key={link.href}>
                {link.href.startsWith("mailto:") ? (
                  <a href={link.href} className={cn(LINK, "inline-flex min-h-10 items-center")}>
                    {link.label}
                  </a>
                ) : (
                  <Link href={link.href as Route} className={cn(LINK, "inline-flex min-h-10 items-center")}>
                    {link.label}
                  </Link>
                )}
              </li>
            ))}
          </ul>
          <div className="mt-8">
            <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="w-full px-6 sm:w-auto">
              Start free
            </CtaLink>
          </div>
        </Container>
      </section>
    </main>
  );
}
