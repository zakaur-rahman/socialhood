import type { Route } from "next";
import Link from "next/link";
import { ArrowRight, KeyRound, ListChecks, ShieldCheck, Timer, Upload, type LucideIcon } from "lucide-react";

import { CONNECT_AI_PATH, mcpUrl } from "@/lib/marketing/connect-ai";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";
import {
  API_KEY_FAQ,
  API_KEY_H1,
  API_KEY_PAGE_PATH,
  KEEP_SAFE,
  KEY_LIMITS,
  KEY_PLAN_ROWS,
  KEY_SCOPES,
  WHEN_TO_USE,
  keyConfigs,
} from "@/lib/marketing/mcp-api-key";
import { MCP_PAGE_PATH } from "@/lib/marketing/mcp-page";
import { faqPageJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, absoluteUrl, appUrl, siteUrl } from "@/lib/marketing/site";

import { Faq } from "../Faq";
import { FinalCta } from "../FinalCta";
import { RelatedCards } from "../GtmPageView";
import { BreadcrumbJsonLd, JsonLd } from "../JsonLd";
import { Ico } from "../landing/Ico";
import { CtaLink, SECTION_EYEBROW } from "../primitives";
import { Code } from "./CodeBlock";

const SAFE_ICONS: LucideIcon[] = [KeyRound, ListChecks, ShieldCheck, Timer, ShieldCheck, ListChecks];

const SECTIONS = [
  { id: "when", label: "When to use a key" },
  { id: "create", label: "Create a key" },
  { id: "config", label: "Add it to your app" },
  { id: "uploads", label: "Uploads" },
  { id: "safe", label: "Keep it safe" },
  { id: "limits", label: "Limits" },
  { id: "faq", label: "Common questions" },
] as const;

/**
 * /developers/mcp/api-key (C-165): connecting Claude Code, Codex, other MCP apps and your own
 * scripts with an API key. Same look as the setup guide (ConnectAiView); the words and numbers are
 * lib/marketing/mcp-api-key.ts, and the limits table reuses connect-ai.ts's PLAN_ROWS. Static.
 */
export function McpApiKeyView({ apiBase }: { apiBase?: string }) {
  const url = mcpUrl(apiBase);
  const configs = keyConfigs(url);
  return (
    <main id="main" tabIndex={-1} className="pp cx flex-1 outline-none">
      <BreadcrumbJsonLd name="Connect with an API key" path={API_KEY_PAGE_PATH} />
      <JsonLd
        data={{ "@context": "https://schema.org", ...faqPageJsonLd(API_KEY_FAQ, siteUrl(), `${absoluteUrl(API_KEY_PAGE_PATH, siteUrl())}#faq`) }}
      />
      <section className="page-head pp-head">
        <div className="wrap pp-head-grid">
          <div>
            <p className={SECTION_EYEBROW}>Developers · MCP</p>
            <h1 className="h-page">{API_KEY_H1}</h1>
            <p className="lede">
              Use an Amplychat API key instead of signing in. It suits Claude Code, Codex, other MCP apps that send a header, and
              your own scripts. A key is part of Pro and Max.
            </p>
            <div className="cx-url">
              <p className="cx-url-label">Server address</p>
              <Code>{url}</Code>
            </div>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={CONNECT_AI_PATH} variant="secondary">
                Sign in instead
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
            <p className="pp-toc-foot">Pro and Max</p>
          </nav>
        </div>
      </section>

      <section id="when" aria-labelledby="when-title" className="band scroll-mt-24">
        <div className="wrap">
          <div className="split-head">
            <h2 id="when-title" className="h-sec">
              When to use a key instead of signing in
            </h2>
            <p className="lede">
              Signing in is the easier way, and it works in claude.ai and ChatGPT as well. Use a key when nobody can sign in.
            </p>
          </div>
          <ul className="mx-list after-head">
            {WHEN_TO_USE.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="cx-note">
            Making a key needs a Pro or Max workspace. A key acts as the member who made it, with that member&apos;s role.
          </p>
        </div>
      </section>

      <section id="create" aria-labelledby="create-title" className="band scroll-mt-24">
        <div className="wrap">
          <div className="split-head">
            <h2 id="create-title" className="h-sec">
              Create a key
            </h2>
            <p className="lede">
              In Amplychat, open Settings › API keys (owners and admins), choose Create API key, name it after the tool and pick
              its scopes. The key is shown once: copy it then.
            </p>
          </div>
          <div role="region" aria-label="The scopes an AI app's key can carry" tabIndex={0} className="cx-table-box after-head">
            <table className="cx-table">
              <caption className="sr-only">The scopes an AI app&apos;s key can carry</caption>
              <thead>
                <tr>
                  <th scope="col">Scope</th>
                  <th scope="col">What the AI app can do</th>
                </tr>
              </thead>
              <tbody>
                {KEY_SCOPES.map((row) => (
                  <tr key={row.scope}>
                    <th scope="row">
                      <code>{row.scope}</code>
                    </th>
                    <td>{row.body}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="cx-note">
            Basic workspace details are always allowed. The same key can also use the <Link href={"/developers/api" as Route}>public API</Link> if you
            add its scopes.
          </p>
        </div>
      </section>

      <section id="config" aria-labelledby="config-title" className="band pp-steps scroll-mt-24">
        <div className="wrap">
          <h2 id="config-title" className="h-sec">
            Add it to your app
          </h2>
          <div className="cx-guides after-head">
            {configs.map((config) => (
              <article key={config.id} id={config.id} aria-labelledby={`${config.id}-title`} className="cx-guide scroll-mt-24">
                <h3 id={`${config.id}-title`}>
                  <Ico icon={KeyRound} />
                  <span>{config.name}</span>
                </h3>
                <p className="cx-who">{config.intro}</p>
                <Code>{config.code}</Code>
                {config.note ? <p className="cx-note">{config.note}</p> : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="uploads" aria-labelledby="uploads-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="uploads-title" className="h-sec">
            Uploads with a key
          </h2>
          <ul className="gcards after-head">
            <li className="gcard">
              <Ico icon={Upload} />
              <h3>Files go straight to storage</h3>
              <p>
                In Claude Code and Codex, Amplychat gives the AI a signed command. The AI runs it where the file is, for example the
                output of ffmpeg, and the file goes to your media library without passing through the API. If your Codex sandbox
                blocks the network, approve the command when it runs.
              </p>
            </li>
          </ul>
        </div>
      </section>

      <section id="safe" aria-labelledby="safe-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="safe-title" className="h-sec">
            Keep your keys safe
          </h2>
          <ul className="gcards after-head">
            {KEEP_SAFE.map((item, index) => (
              <li key={item.title} className="gcard">
                <Ico icon={SAFE_ICONS[index] ?? ShieldCheck} />
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="limits" aria-labelledby="limits-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="limits-title" className="h-sec">
            Limits
          </h2>
          <ul className="mx-list after-head">
            {KEY_LIMITS.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <div role="region" aria-label="Daily limits by plan" tabIndex={0} className="cx-table-box mx-gap">
            <table className="cx-table">
              <caption className="sr-only">Daily limits by plan</caption>
              <thead>
                <tr>
                  <th scope="col">Per workspace</th>
                  <th scope="col">Free</th>
                  <th scope="col">Pro</th>
                  <th scope="col">Max</th>
                </tr>
              </thead>
              <tbody>
                {KEY_PLAN_ROWS.map((row) => (
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
            Days are UTC. These count across all your AI connections, keys and sign-ins together. <Link href={PRICING_PATH as Route}>See plans</Link>.
          </p>
        </div>
      </section>

      <Faq items={API_KEY_FAQ} id="faq" lede="Short answers about connecting with a key." allLink={false} />

      <RelatedCards
        links={[
          { label: "Set up with sign-in", href: CONNECT_AI_PATH },
          { label: "What it can do", href: MCP_PAGE_PATH },
          { label: "Public API", href: "/developers/api" },
          { label: "Security", href: "/security" },
        ]}
      />
      <FinalCta />
    </main>
  );
}
