import { ArrowRight, Check, CircleDollarSign, Minus, Scale, TrendingUp, Sparkles, MessagesSquare } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Callout } from "@/components/site/Callout";
import { legalDate } from "@/lib/legal";
import {
  ALTERNATIVES,
  ALTERNATIVES_PATH,
  ALTERNATIVE_COMPETITORS,
  MANYCHAT_STRENGTHS,
  WHY_SWITCH,
  alternativesChecked,
  type Alternative,
} from "@/lib/marketing/alternatives";
import { competitorsNote, latestChecked } from "@/lib/marketing/competitor-note";
import { COMPARE_MANYCHAT, COMPARE_PATH, PRICING_PATH } from "@/lib/marketing/gtm-pages";
import { breadcrumbTrailJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, SITE_NAME, absoluteUrl, appUrl, siteUrl } from "@/lib/marketing/site";

import { FinalCta } from "./FinalCta";
import { RelatedCards } from "./GtmPageView";
import { JsonLd } from "./JsonLd";
import { Ico } from "./landing/Ico";
import { CtaLink, SECTION_EYEBROW } from "./primitives";

const WHY_ICONS = [TrendingUp, Sparkles, MessagesSquare];
const CHANNEL_COLOUR = { instagram: "var(--ig)", whatsapp: "var(--wa)", web: "var(--web)" } as const;
const CHANNEL_NAME = { instagram: "Instagram", whatsapp: "WhatsApp", web: "Website chat" } as const;

function slug(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");
}

/** The page's list as schema.org ItemList, unordered: the alphabetical order isn't a ranking. */
export function alternativesJsonLd(origin: string = siteUrl()): Record<string, unknown> {
  const url = absoluteUrl(ALTERNATIVES_PATH, origin);
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "@id": `${url}#list`,
    name: "Manychat alternatives",
    url,
    itemListOrder: "https://schema.org/ItemListUnordered",
    numberOfItems: ALTERNATIVES.length,
    itemListElement: ALTERNATIVES.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      url: absoluteUrl(item.href, origin),
    })),
  };
}

function Channels({ item }: { item: Alternative }) {
  return (
    <ul className="alt-chans" aria-label="Channels">
      {item.channels.map((channel) => (
        <li key={channel} style={{ "--c": CHANNEL_COLOUR[channel] } as CSSProperties}>
          <PlatformGlyph platform={channel} />
          <span>{CHANNEL_NAME[channel]}</span>
        </li>
      ))}
    </ul>
  );
}

function AltCard({ item }: { item: Alternative }) {
  const checked = item.ours ? null : legalDate(latestChecked(item.page));
  return (
    <article id={slug(item.name)} aria-labelledby={`${slug(item.name)}-t`} className={item.ours ? "alt-card is-ours scroll-mt-24" : "alt-card scroll-mt-24"}>
      <header className="alt-card-h">
        <h3 id={`${slug(item.name)}-t`}>{item.name}</h3>
        <Channels item={item} />
      </header>
      <p className="alt-best">
        <span>Suits</span> {item.bestFor}
      </p>
      <div className="alt-cols">
        <div>
          <h4>Strengths</h4>
          <ul className="alt-list is-plus">
            {item.strengths.map((line) => (
              <li key={line}>
                <Check size={16} strokeWidth={2} aria-hidden focusable="false" />
                {line}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4>Limits</h4>
          <ul className="alt-list is-minus">
            {item.limits.map((line) => (
              <li key={line}>
                <Minus size={16} strokeWidth={2} aria-hidden focusable="false" />
                {line}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <footer className="alt-card-f">
        <p className="alt-price">
          <CircleDollarSign size={16} strokeWidth={1.75} aria-hidden focusable="false" />
          <span>
            {item.price}
            {checked ? <span className="alt-date"> Checked on {checked}.</span> : <span className="alt-date"> Checked against our code.</span>}
          </span>
        </p>
        <Link href={item.href as Route} className="btn btn-line alt-go">
          {item.ours ? `${SITE_NAME} vs Manychat` : `${SITE_NAME} vs ${item.name}`} <ArrowRight className="size-4" aria-hidden />
        </Link>
      </footer>
    </article>
  );
}

/**
 * Manychat alternatives (C-163): who looks for one and why (from Manychat's own pages, as the
 * comparison records them), where Manychat stays stronger, a table at a glance, then each tool as a
 * card with what it suits, strengths, limits and its starting price with the date read, linking to
 * the full comparison. Alphabetical, said not to be a ranking; Amplychat with its limits like the
 * others. The plural trademark note, related pages and the night close. ItemList and breadcrumbs.
 */
export function AlternativesView() {
  const checked = legalDate(alternativesChecked());
  const note = competitorsNote(ALTERNATIVE_COMPETITORS, alternativesChecked());
  const toc = [
    { href: "#why", label: "Why people look for an alternative" },
    { href: "#at-a-glance", label: "At a glance" },
    { href: "#alternatives", label: "The alternatives" },
    { href: "#how-we-checked", label: "How we checked" },
  ];
  return (
    <main id="main" tabIndex={-1} className="pp alts flex-1 outline-none">
      <JsonLd
        data={breadcrumbTrailJsonLd([
          { name: "Compare", path: COMPARE_PATH },
          { name: "Manychat alternatives", path: ALTERNATIVES_PATH },
        ])}
      />
      <JsonLd data={alternativesJsonLd()} />
      <section className="page-head pp-head">
        <div className="wrap pp-head-grid">
          <div>
            <p className={SECTION_EYEBROW}>Compare</p>
            <h1 className="h-page">Manychat alternatives for Instagram and WhatsApp</h1>
            <p className="lede">
              Nine tools people consider instead of Manychat, {SITE_NAME} among them. For each: who it suits, its strengths and
              limits, and its starting price, from the vendor&apos;s own pages with the date we read them.
            </p>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={COMPARE_MANYCHAT.path} variant="secondary">
                {COMPARE_MANYCHAT.name}
              </CtaLink>
            </div>
          </div>
          <nav className="pp-toc" aria-label="On this page">
            <p className="pp-toc-h">On this page</p>
            <ul>
              {toc.map((link) => (
                <li key={link.href}>
                  <a href={link.href}>{link.label}</a>
                </li>
              ))}
            </ul>
            {checked ? <p className="pp-toc-foot">Sources read on {checked}</p> : null}
          </nav>
        </div>
      </section>

      <section id="why" aria-labelledby="why-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="why-title" className="h-sec">
            Why people look for an alternative
          </h2>
          <ul className="gcards is-3 after-head">
            {WHY_SWITCH.map((item, index) => (
              <li key={item.title} className="gcard">
                <Ico icon={WHY_ICONS[index]} className={index === 1 ? "ico-ai" : undefined} />
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </li>
            ))}
          </ul>
          <Callout tone="means" icon={Scale} title="Where Manychat stays strong" className="alt-fair">
            <p>{MANYCHAT_STRENGTHS}</p>
          </Callout>
        </div>
      </section>

      <section id="at-a-glance" aria-labelledby="glance-title" className="band scroll-mt-24">
        <div className="wrap">
          <div className="split-head">
            <h2 id="glance-title" className="h-sec">
              At a glance
            </h2>
            <p className="lede">In alphabetical order. The order isn&apos;t a ranking: the right tool depends on your channels and how you sell.</p>
          </div>
          <div role="region" aria-label="Manychat alternatives at a glance" tabIndex={0} className="ctable-box after-head">
            <table className="ctable alt-table">
              <caption className="sr-only">Manychat alternatives at a glance</caption>
              <thead>
                <tr>
                  <th scope="col">Tool</th>
                  <th scope="col">Suits</th>
                  <th scope="col">Starting price</th>
                </tr>
              </thead>
              <tbody>
                {ALTERNATIVES.map((item) => (
                  <tr key={item.name} className={item.ours ? "ours-row" : undefined}>
                    <th scope="row">
                      <a href={`#${slug(item.name)}`}>{item.name}</a>
                    </th>
                    <td>{item.bestFor}</td>
                    <td>{item.price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section id="alternatives" aria-labelledby="alts-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="alts-title" className="h-sec">
            The alternatives
          </h2>
          <ul className="alt-cards after-head">
            {ALTERNATIVES.map((item) => (
              <li key={item.name}>
                <AltCard item={item} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="how-we-checked" aria-labelledby="checked-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="checked-title" className="h-sec">
            How we checked
          </h2>
          <div className="know after-head">
            <Callout tone="info">
              <ul className="alt-how">
                <li>Every line about a vendor comes from our comparison with it, which lists the vendor&apos;s own pages and the date we read each one.</li>
                <li>&ldquo;Weren&apos;t found&rdquo; means we didn&apos;t see it on the pages we read, not that the product lacks it.</li>
                <li>Prices and plans change and can differ by region and billing period, so check each vendor&apos;s site before you decide.</li>
                <li>Our own lines are checked against our code. Meta&apos;s WhatsApp fees are separate from every plan here.</li>
              </ul>
            </Callout>
            <div className="fnote">
              <h3>Trademarks</h3>
              <p className="fnote-tm alt-tm">
                {note.text}{" "}
                <a href={`mailto:${note.email}`} className="tlink">
                  {note.email}
                </a>
                .
              </p>
            </div>
          </div>
        </div>
      </section>

      <RelatedCards
        links={[
          { label: "All comparisons", href: COMPARE_PATH },
          { label: "Switch from Manychat", href: "/switch-from-manychat" },
          { label: "Plans and limits", href: PRICING_PATH },
          { label: "Meta messaging glossary", href: "/glossary" },
        ]}
      />
      <FinalCta />
    </main>
  );
}
