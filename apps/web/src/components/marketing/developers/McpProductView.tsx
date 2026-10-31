import type { Route } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Bot,
  Eye,
  Hand,
  ListChecks,
  MessageSquareQuote,
  ScrollText,
  ShieldCheck,
  Timer,
  type LucideIcon,
} from "lucide-react";

import { PLAN_ROWS, SAFETY } from "@/lib/marketing/connect-ai";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";
import {
  ASKS,
  CONFIRM_LINE,
  HOW_STEPS,
  MCP_API_KEY_PATH,
  MCP_PAGE_FAQ,
  MCP_PAGE_H1,
  MCP_PAGE_PATH,
  MCP_SETUP_PATH,
  WHERE_CARDS,
} from "@/lib/marketing/mcp-page";
import { faqPageJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, absoluteUrl, appUrl, siteUrl } from "@/lib/marketing/site";

import { Faq } from "../Faq";
import { FinalCta } from "../FinalCta";
import { RelatedCards } from "../GtmPageView";
import { BreadcrumbJsonLd, JsonLd } from "../JsonLd";
import { Ico } from "../landing/Ico";
import { CtaLink, SECTION_EYEBROW } from "../primitives";

const SAFETY_ICONS: LucideIcon[] = [Hand, Timer, ShieldCheck, Eye, ScrollText, ListChecks];

const SECTIONS = [
  { id: "where", label: "Where you can use it" },
  { id: "ask", label: "What you can ask" },
  { id: "how", label: "How it works" },
  { id: "plans", label: "Plans" },
  { id: "safety", label: "Safety" },
  { id: "faq", label: "Common questions" },
] as const;

/**
 * /mcp (C-165): what the MCP server is for business owners and creators, where it can be used,
 * what to ask, plans and safety, in the C-159 product-page look (the same classes as
 * ConnectAiView). The words are lib/marketing/mcp-page.ts; plans and safety are connect-ai.ts's.
 * Static.
 */
export function McpProductView() {
  return (
    <main id="main" tabIndex={-1} className="pp cx mx flex-1 outline-none">
      <BreadcrumbJsonLd name="Use Amplychat from your AI app" path={MCP_PAGE_PATH} />
      <JsonLd
        data={{ "@context": "https://schema.org", ...faqPageJsonLd(MCP_PAGE_FAQ, siteUrl(), `${absoluteUrl(MCP_PAGE_PATH, siteUrl())}#faq`) }}
      />
      <section className="page-head pp-head">
        <div className="wrap pp-head-grid">
          <div>
            <p className={SECTION_EYEBROW}>MCP</p>
            <h1 className="h-page">{MCP_PAGE_H1}</h1>
            <p className="lede">
              Ask your AI assistant to schedule a Reel for Friday at 6 pm, sum up this week&apos;s DMs or tell you which posts did best.
              It works as you, inside Amplychat&apos;s own rules and plan limits, and every action is recorded.
            </p>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={MCP_SETUP_PATH} variant="secondary">
                Set it up
              </CtaLink>
            </div>
          </div>
          <nav className="pp-toc" aria-label="On this page">
            <p className="pp-toc-h">On this page</p>
            <ul>
              {SECTIONS.map((section) => (
                <li key={section.id}>
                  <a href={`#${section.id}`}>{section.label}</a>
                </li>
              ))}
            </ul>
            <p className="pp-toc-foot">Instagram publishing, inbox, comments and analytics</p>
          </nav>
        </div>
      </section>

      <section id="where" aria-labelledby="where-title" className="band scroll-mt-24">
        <div className="wrap">
          <div className="split-head">
            <h2 id="where-title" className="h-sec">
              Where you can use it
            </h2>
            <p className="lede">
              MCP is the standard these apps use to connect to other services. One address works in all of them.
            </p>
          </div>
          <ul className="gcards after-head">
            {WHERE_CARDS.map((card) => (
              <li key={card.id} className="gcard">
                <Ico icon={Bot} />
                <h3>{card.title}</h3>
                <p>{card.body}</p>
                {card.note ? <p className="cx-note">{card.note}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="ask" aria-labelledby="ask-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="ask-title" className="h-sec">
            What you can ask
          </h2>
          <ul className="mx-asks after-head">
            {ASKS.map((ask) => (
              <li key={ask.prompt} className="mx-ask">
                <MessageSquareQuote className="mx-ask-ico" aria-hidden />
                <blockquote>{ask.prompt}</blockquote>
                <p>{ask.result}</p>
                {ask.plan ? <p className="mx-plan">{ask.plan}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="how" aria-labelledby="how-title" className="band pp-steps scroll-mt-24">
        <div className="wrap">
          <div className="split-head">
            <h2 id="how-title" className="h-sec">
              How it works
            </h2>
            <p className="lede">{CONFIRM_LINE}</p>
          </div>
          <ol className="mx-steps after-head">
            {HOW_STEPS.map((step) => (
              <li key={step.title} className="gcard">
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>
          <p className="cx-note">
            <Link href={MCP_SETUP_PATH as Route}>Open the setup guide</Link>, or <Link href={MCP_API_KEY_PATH as Route}>connect with an API key</Link> if you
            use Claude Code or Codex.
          </p>
        </div>
      </section>

      <section id="plans" aria-labelledby="plans-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="plans-title" className="h-sec">
            Plans
          </h2>
          <div role="region" aria-label="What each plan includes for AI apps" tabIndex={0} className="cx-table-box after-head">
            <table className="cx-table">
              <caption className="sr-only">What each plan includes for AI apps</caption>
              <thead>
                <tr>
                  <th scope="col">AI apps</th>
                  <th scope="col">Free</th>
                  <th scope="col">Pro</th>
                  <th scope="col">Max</th>
                </tr>
              </thead>
              <tbody>
                {PLAN_ROWS.map((row) => (
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
          <p className="cx-note">
            Scheduled posts count toward your plan&apos;s monthly posts, as in the app. <Link href={PRICING_PATH as Route}>See all plans</Link>.
          </p>
        </div>
      </section>

      <section id="safety" aria-labelledby="safety-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="safety-title" className="h-sec">
            Safety
          </h2>
          <ul className="gcards after-head">
            {SAFETY.map((item, index) => (
              <li key={item.title} className="gcard">
                <Ico icon={SAFETY_ICONS[index] ?? ShieldCheck} />
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Faq items={MCP_PAGE_FAQ} id="faq" lede="Short answers about using Amplychat from an AI app." allLink={false} />

      <RelatedCards
        links={[
          { label: "Set up your AI app", href: MCP_SETUP_PATH },
          { label: "Connect with an API key", href: MCP_API_KEY_PATH },
          { label: "Public API", href: "/developers/api" },
          { label: "Pricing", href: PRICING_PATH },
        ]}
      />
      <FinalCta />
    </main>
  );
}
