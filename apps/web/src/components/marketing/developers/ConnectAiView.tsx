import type { Route } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Bot,
  CalendarClock,
  Clapperboard,
  Eye,
  Hand,
  Inbox,
  Library,
  ListChecks,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Timer,
  type LucideIcon,
} from "lucide-react";

import { CONNECT_AI_FAQ, CONNECT_AI_META, CONNECT_AI_PATH, CAPABILITIES, PLAN_ROWS, SAFETY, clientGuides, mcpUrl, type ClientGuide } from "@/lib/marketing/connect-ai";
import { API_KEY_PAGE_PATH } from "@/lib/marketing/mcp-api-key";
import { MCP_PAGE_PATH } from "@/lib/marketing/mcp-page";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";
import { faqPageJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, absoluteUrl, appUrl, siteUrl } from "@/lib/marketing/site";

import { Faq } from "../Faq";
import { FinalCta } from "../FinalCta";
import { RelatedCards } from "../GtmPageView";
import { BreadcrumbJsonLd, JsonLd } from "../JsonLd";
import { Ico } from "../landing/Ico";
import { CtaLink, SECTION_EYEBROW } from "../primitives";

const CAPABILITY_ICONS: Record<string, LucideIcon> = {
  "Schedule Instagram posts": CalendarClock,
  "Edit a video, then post it": Clapperboard,
  "Read your inbox": Inbox,
  "Comments and analytics": BarChart3,
  "Knowledge and automations": Library,
  "Ask Amplychat": Sparkles,
};

const SAFETY_ICONS: LucideIcon[] = [Hand, Timer, ShieldCheck, Eye, ScrollText, ListChecks];

/** The guides that offer a key as the other way in. */
const KEY_GUIDES: ReadonlySet<string> = new Set(["claude-code", "codex"]);

const SECTIONS = [
  { id: "what-you-can-do", label: "What you can do" },
  { id: "set-up", label: "Set it up" },
  { id: "plans", label: "Plans" },
  { id: "safety", label: "Safety" },
  { id: "faq", label: "Common questions" },
] as const;

export function Code({ children }: { children: string }) {
  return (
    <pre className="cx-code" tabIndex={0}>
      <code>{children}</code>
    </pre>
  );
}

function Guide({ guide }: { guide: ClientGuide }) {
  return (
    <article id={guide.id} aria-labelledby={`${guide.id}-title`} className="cx-guide scroll-mt-24">
      <h3 id={`${guide.id}-title`}>
        <Ico icon={Bot} />
        <span>{guide.name}</span>
      </h3>
      <p className="cx-who">{guide.who}</p>
      <ol className="cx-steps">
        {guide.steps.map((step) => (
          <li key={step.text}>
            <p>{step.text}</p>
            {step.code ? <Code>{step.code}</Code> : null}
          </li>
        ))}
      </ol>
      {guide.note ? <p className="cx-note">{guide.note}</p> : null}
      {KEY_GUIDES.has(guide.id) ? (
        <p className="cx-note">
          <Link href={API_KEY_PAGE_PATH as Route}>Using an API key instead</Link>
        </p>
      ) : null}
    </article>
  );
}

/**
 * /developers/mcp (C-165 phase C): how to connect Amplychat to Claude, ChatGPT and Codex, in the
 * C-159 product-page look (head beside an "On this page" card, icon cards, the closing night band).
 * Static; the content and its rules are lib/marketing/connect-ai.ts.
 */
export function ConnectAiView({ apiBase }: { apiBase?: string }) {
  const url = mcpUrl(apiBase);
  const guides = clientGuides(url);
  return (
    <main id="main" tabIndex={-1} className="pp cx flex-1 outline-none">
      <BreadcrumbJsonLd name="Connect AI apps" path={CONNECT_AI_PATH} />
      <JsonLd
        data={{ "@context": "https://schema.org", ...faqPageJsonLd(CONNECT_AI_FAQ, siteUrl(), `${absoluteUrl(CONNECT_AI_PATH, siteUrl())}#faq`) }}
      />
      <section className="page-head pp-head">
        <div className="wrap pp-head-grid">
          <div>
            <p className={SECTION_EYEBROW}>Developers · MCP</p>
            <h1 className="h-page">{CONNECT_AI_META.title}</h1>
            <p className="lede">
              Ask your AI assistant to schedule a Reel for Friday at 6 pm, or to sum up this week&apos;s DMs. It works through
              Amplychat&apos;s own rules, limits and plan, as you, and every action is recorded.
            </p>
            <div className="cx-url">
              <p className="cx-url-label">
                Server address
              </p>
              <Code>{url}</Code>
            </div>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={PRICING_PATH} variant="secondary">
                See plans and limits
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

      <section id="what-you-can-do" aria-labelledby="what-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="what-title" className="h-sec">
            What you can do
          </h2>
          <ul className="gcards after-head">
            {CAPABILITIES.map((item) => (
              <li key={item.title} className="gcard">
                <Ico icon={CAPABILITY_ICONS[item.title] ?? Sparkles} className={item.ai ? "ico-ai" : undefined} />
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="set-up" aria-labelledby="setup-title" className="band pp-steps scroll-mt-24">
        <div className="wrap">
          <div className="split-head">
            <h2 id="setup-title" className="h-sec">
              Set it up
            </h2>
            <p className="lede">
              One connection is one workspace, as one member. You choose the workspace and what the app may do when you allow it.
            </p>
          </div>
          <nav className="cx-jump after-head" aria-label="Choose your app">
            {guides.map((guide) => (
              <a key={guide.id} href={`#${guide.id}`}>
                {guide.name.split(" (")[0]}
              </a>
            ))}
          </nav>
          <div className="cx-guides">
            {guides.map((guide) => (
              <Guide key={guide.id} guide={guide} />
            ))}
          </div>
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
          <p className="cx-note">Scheduled posts count toward your plan&apos;s monthly posts, as in the app.</p>
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

      <Faq items={CONNECT_AI_FAQ} id="faq" lede="Short answers about connecting AI apps." allLink={false} />

      <RelatedCards
        links={[
          { label: "What Amplychat does in your AI app", href: MCP_PAGE_PATH },
          { label: "Connect with an API key", href: API_KEY_PAGE_PATH },
          { label: "Public API", href: "/developers/api" },
          { label: "Publishing", href: "/features/publishing" },
          { label: "Pricing", href: PRICING_PATH },
          { label: "Security", href: "/security" },
        ]}
      />
      <FinalCta />
    </main>
  );
}
