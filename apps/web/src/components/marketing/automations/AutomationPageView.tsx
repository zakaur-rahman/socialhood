import { ArrowLeft, ArrowRight, CalendarCheck, ChevronDown, ExternalLink, Layers, MessageCircleQuestionMark, Sparkles } from "lucide-react";
import type { Metadata, Route } from "next";
import Link from "next/link";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { GuideH2 } from "@/components/marketing/guides/blocks";
import { TocNav, type TocItem } from "@/components/site/TocNav";
import { PLAN_NAME } from "@/lib/copy";
import {
  AUTOMATIONS_PATH,
  AUTOMATION_PAGES,
  CHANNEL_NAME,
  automationDate,
  type AutomationChannel,
  type AutomationPage,
} from "@/lib/marketing/automation-pages";
import { sectionId } from "@/lib/marketing/guides/types";
import { GUIDE_AUTHOR } from "@/lib/marketing/guides/types";
import { articleJsonLd, breadcrumbTrailJsonLd, pageMetadata } from "@/lib/marketing/seo";
import { FEATURES_PATH, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { ExplainerMotion } from "../explainers/ExplainerMotion";
import { FinalCta } from "../FinalCta";
import { JsonLd } from "../JsonLd";
import { Ico } from "../landing/Ico";
import { CtaLink, SECTION_EYEBROW } from "../primitives";
import { AutomationSceneView, sceneNeedsLandingScript } from "./scenes";

/** The sections every automation page adds after its body, in order. */
export const LIMITS_HEADING = "Plan limits and AI credits";
export const FAQ_HEADING = "Common questions";
export const SOURCES_HEADING = "Meta's sources";
const FAQ_ID = sectionId(FAQ_HEADING);

const COLOUR: Record<AutomationChannel, string> = { instagram: "var(--ig)", whatsapp: "var(--wa)", web: "var(--web)" };

/** A channel's own mark in its colour (the site's motif). */
export function ChannelMark({ channel, className }: { channel: AutomationChannel; className?: string }) {
  return (
    <Ico className={className ? `ico-mark ${className}` : "ico-mark"} style={{ "--c": COLOUR[channel] } as CSSProperties}>
      <PlatformGlyph platform={channel} />
    </Ico>
  );
}

/** A page's metadata: its own title and description, with its dates for Open Graph (og:type article). */
export function automationMetadata(page: AutomationPage): Metadata {
  return pageMetadata({
    title: page.title,
    description: page.description,
    path: page.path,
    article: { publishedTime: page.published, modifiedTime: page.updated, authors: [GUIDE_AUTHOR], tags: [CHANNEL_NAME[page.channel], "Automations"] },
  });
}

/** The page's contents: the body's sections, then the template's. */
export function automationToc(page: AutomationPage): TocItem[] {
  return [
    ...page.sections.map((label) => ({ id: sectionId(label), label })),
    { id: sectionId(LIMITS_HEADING), label: LIMITS_HEADING },
    { id: FAQ_ID, label: FAQ_HEADING },
    ...(page.sources.length ? [{ id: sectionId(SOURCES_HEADING), label: SOURCES_HEADING }] : []),
  ];
}

/** The pages to read next: the matching guide and audience page, pricing, features, then the page's own extras. */
export function automationNext(page: AutomationPage) {
  const links = [page.guide, page.audience, { label: "Plans and limits", href: "/pricing" }, { label: "Every feature", href: FEATURES_PATH }, ...page.related];
  return links.filter((link, index) => links.findIndex((other) => other.href === link.href) === index);
}

/**
 * One automation or channel page (C-163), on the guides' reading layout (C-159: `main.guide`, the
 * article beside a sticky side column from 1060 px, the reading-progress bar, question cards, "Keep
 * reading" on the deeper paper and the night close). Between the head and the article, the page's
 * product scene at the container's width. After the body, from the page's data: the plan limits table
 * (plan-table.json) with what uses AI credits, the page's own questions, and Meta's pages behind its
 * rules with the date they were read. Structured data: an Article with a FAQPage (the questions are this
 * page's only) and a Home, Automations, page breadcrumb. Server-rendered; one idle island
 * (ExplainerMotion) marks the contents and plays the scene once.
 */
export function AutomationPageView({ page }: { page: AutomationPage }) {
  const { Body } = page;
  const toc = automationToc(page);
  const others = AUTOMATION_PAGES.filter((other) => other.path !== page.path);
  return (
    <main id="main" tabIndex={-1} className="guide xp ap flex-1 outline-none">
      <JsonLd
        data={articleJsonLd({
          path: page.path,
          title: page.title,
          description: page.description,
          published: page.published,
          updated: page.updated,
          author: GUIDE_AUTHOR,
          tags: [CHANNEL_NAME[page.channel], "Automations"],
          faq: page.faq,
        })}
      />
      <JsonLd
        data={breadcrumbTrailJsonLd([
          { name: "Automations", path: AUTOMATIONS_PATH },
          { name: page.name, path: page.path },
        ])}
      />
      <article aria-labelledby="ap-title" className="g-article">
        <div className="g-progress" data-toc-progress="" aria-hidden />
        <header className="wrap g-head">
          <Link href={AUTOMATIONS_PATH as Route} className="g-back">
            <ArrowLeft size={16} strokeWidth={1.75} aria-hidden focusable="false" /> All automations
          </Link>
          <p className={SECTION_EYEBROW}>{CHANNEL_NAME[page.channel]}</p>
          <h1 id="ap-title" className="h-page g-h1">
            {page.h1}
          </h1>
          <p className="lede g-lede">{page.lede}</p>
          <div className="g-meta">
            <ChannelMark channel={page.channel} />
            <p className="g-byline">
              <span>By {GUIDE_AUTHOR}</span>
              <span aria-hidden> · </span>
              <span>
                Updated <time dateTime={page.updated}>{automationDate(page.updated)}</time>
              </span>
            </p>
          </div>
        </header>

        <div className="wrap ap-scene">
          <AutomationSceneView scene={page.scene} />
        </div>

        <div className="wrap g-grid">
          <div className="g-main">
            <details className="g-toc-m">
              <summary>
                On this page <ChevronDown size={16} strokeWidth={1.75} aria-hidden focusable="false" />
              </summary>
              <TocNav items={toc} label="On this page" />
            </details>

            <div data-guide-body="" className="gprose">
              <Body />

              <GuideH2>{LIMITS_HEADING}</GuideH2>
              <div className="ap-lim-box">
                <table className="ap-lim">
                  <caption className="sr-only">{LIMITS_HEADING}: limits on each plan</caption>
                  <thead>
                    <tr>
                      <th scope="col">Limit</th>
                      <th scope="col">{PLAN_NAME.free}</th>
                      <th scope="col">{PLAN_NAME.pro}</th>
                      <th scope="col">{PLAN_NAME.max}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.limits.map((row) => (
                      <tr key={row.label}>
                        <th scope="row">{row.label}</th>
                        <td>{row.free}</td>
                        <td>{row.pro}</td>
                        <td>{row.max}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul>
                {page.credits.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p>
                Every limit for each plan is on the <Link href="/pricing">pricing page</Link>, and every feature with its status on the{" "}
                <Link href={FEATURES_PATH}>features page</Link>.
              </p>
            </div>

            <section aria-labelledby={FAQ_ID} className="g-faq">
              <h2 id={FAQ_ID} className="g-faq-h">
                {FAQ_HEADING}
              </h2>
              <dl className="g-qas">
                {page.faq.map((item) => (
                  <div key={item.question} className="g-qa">
                    <dt>
                      <Ico icon={MessageCircleQuestionMark} />
                      <span>{item.question}</span>
                    </dt>
                    <dd>{item.answer}</dd>
                  </div>
                ))}
              </dl>
            </section>

            {page.sources.length ? (
              <section aria-labelledby={sectionId(SOURCES_HEADING)} className="ap-src">
                <h2 id={sectionId(SOURCES_HEADING)} className="ap-src-h">
                  {SOURCES_HEADING}
                </h2>
                <p className="ap-src-p">The rules above come from Meta&apos;s own pages. Meta changes them from time to time; its page wins.</p>
                <ul>
                  {page.sources.map((source) => (
                    <li key={source.url}>
                      <a href={source.url} rel="noopener noreferrer" target="_blank">
                        {source.label}
                        <ExternalLink className="size-3.5" aria-hidden />
                        <span className="sr-only"> (opens in a new tab)</span>
                      </a>
                      <span>
                        Read <time dateTime={source.read}>{automationDate(source.read)}</time>
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>

          <aside className="g-side" aria-label="About this page">
            <div className="g-side-in">
              <TocNav items={toc} className="toc-side" />
              <dl className="g-facts">
                <div>
                  <dt>
                    <Layers size={16} strokeWidth={1.75} aria-hidden focusable="false" /> Channel
                  </dt>
                  <dd>{CHANNEL_NAME[page.channel]}</dd>
                </div>
                <div>
                  <dt>
                    <Sparkles size={16} strokeWidth={1.75} aria-hidden focusable="false" /> Plans
                  </dt>
                  <dd>Free, Pro and Max</dd>
                </div>
                <div>
                  <dt>
                    <CalendarCheck size={16} strokeWidth={1.75} aria-hidden focusable="false" /> Updated
                  </dt>
                  <dd>
                    <time dateTime={page.updated}>{automationDate(page.updated)}</time>
                  </dd>
                </div>
              </dl>
              <div className="g-try">
                <p className="g-try-t">Try it on your own account</p>
                <p className="g-try-p">The Free plan needs no card.</p>
                <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="g-try-btn">
                  Start free <ArrowRight className="size-4" aria-hidden />
                </CtaLink>
              </div>
            </div>
          </aside>
        </div>
      </article>

      <section aria-labelledby="ap-next-title" className="g-next">
        <div className="wrap">
          <h2 id="ap-next-title" className="h-sec">
            Keep reading
          </h2>
          <ul className="g-also ap-also" aria-label="Related pages">
            {automationNext(page).map((link) => (
              <li key={link.href}>
                <Link href={link.href as Route} className="btn btn-line">
                  {link.label} <ArrowRight className="size-4" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
          <h3 className="ap-next-h">More automations</h3>
          <ul className="g-cards ap-cards">
            {others.map((other) => (
              <li key={other.path}>
                <AutomationCard page={other} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <FinalCta />
      <ExplainerMotion scenes={sceneNeedsLandingScript(page.scene)} />
    </main>
  );
}

/** An automation page as a card (the hub and "More automations"): its channel, title (the card's one link) and line. */
export function AutomationCard({ page, headingLevel = 3 }: { page: AutomationPage; headingLevel?: 3 | 4 }) {
  const Heading = headingLevel === 3 ? "h3" : "h4";
  return (
    <article className="g-card ap-card">
      <div className="g-card-b">
        <div className="g-card-top">
          <ChannelMark channel={page.channel} />
          <span className="ap-card-ch">{CHANNEL_NAME[page.channel]}</span>
        </div>
        <Heading className="g-card-t">
          {/* The whole card is the link's target; the title is its name. */}
          <Link href={page.path as Route}>{page.name}</Link>
        </Heading>
        <p className="g-card-p">{page.description}</p>
        <p className="g-card-m">
          <span>Read how it works</span>
          <span aria-hidden className="g-card-go">
            <ArrowRight size={16} strokeWidth={1.75} aria-hidden focusable="false" />
          </span>
        </p>
      </div>
    </article>
  );
}
