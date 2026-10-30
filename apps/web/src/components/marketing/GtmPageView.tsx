import { ArrowRight, Info } from "lucide-react";
import type { Route } from "next";
import Image from "next/image";
import Link from "next/link";

import { StatusChip } from "@/components/site/StatusChip";
import { legalDate } from "@/lib/legal";
import { competitorNote, latestChecked } from "@/lib/marketing/competitor-note";
import { COMPARE_PATH, PRICING_PATH, type Block, type Cell, type GtmPage } from "@/lib/marketing/gtm-pages";
import { breadcrumbTrailJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, SITE_NAME, appUrl } from "@/lib/marketing/site";

import { FinalCta } from "./FinalCta";
import { BreadcrumbJsonLd, JsonLd } from "./JsonLd";
import { Ico } from "./landing/Ico";
import { SETUP_STEPS } from "./landing/Steps";
import { AI_TITLES, VERDICT_ICONS, cardIcon } from "./page-icons";
import { CtaLink, SECTION_EYEBROW } from "./primitives";
import { SHOTS } from "./shots";

/** The ids the "On this page" card links to. */
const SIDE_BY_SIDE = "side-by-side";
const BEFORE_YOU_DECIDE = "before-you-decide";

function CellView({ cell }: { cell: Cell }) {
  return (
    <>
      <StatusChip status={cell.status} />
      {cell.text ? <span className="cell-t">{cell.text}</span> : null}
    </>
  );
}

/**
 * The comparison table (C-159): a sticky header row on a wide screen, our column on a quiet tone
 * step, each status as a chip with its icon. On a phone it scrolls inside its own box (the page
 * never scrolls sideways) with the feature column held at the left edge.
 */
function Compare({ page }: { page: GtmPage }) {
  if (!page.compare) return null;
  const { competitor, caption, rows } = page.compare;
  return (
    <section id={SIDE_BY_SIDE} aria-labelledby="compare-title" className="band scroll-mt-24">
      <div className="wrap">
        <h2 id="compare-title" className="h-sec">
          Side by side
        </h2>
        <div role="region" aria-label={caption} tabIndex={0} className="ctable-box">
          <table className="ctable">
            <caption className="sr-only">{caption}</caption>
            <colgroup>
              <col className="c-feat" />
              <col />
              <col />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Feature</th>
                <th scope="col" className="ours">
                  {SITE_NAME}
                </th>
                <th scope="col">{competitor}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.feature}>
                  <th scope="row">{row.feature}</th>
                  <td className="ours">
                    <CellView cell={row.ours} />
                  </td>
                  <td>
                    <CellView cell={row.theirs} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

/** "Which fits you" on a comparison: two verdict cards of equal weight, the competitor's first. */
function Verdict({ block }: { block: Block }) {
  return (
    <ul className="verdict after-head">
      {block.items.map((item) => {
        const ours = item.title.startsWith(SITE_NAME);
        return (
          <li key={item.title} className={ours ? "vcard is-ours" : "vcard"}>
            <h3>
              <Ico icon={ours ? VERDICT_ICONS.ours : VERDICT_ICONS.theirs} />
              <span>{item.title}</span>
            </h3>
            <p>{item.body}</p>
          </li>
        );
      })}
    </ul>
  );
}

/** A block's points as icon cards: the icon beside the title, the text under it (the landing's `.fcard`). */
function Cards({ block }: { block: Block }) {
  return (
    <ul className="gcards after-head">
      {block.items.map((item) => (
        <li key={item.title} className="gcard">
          <Ico icon={cardIcon(item.title)} className={AI_TITLES.has(item.title) ? "ico-ai" : undefined} />
          <h3>{item.title}</h3>
          <p>{item.body}</p>
        </li>
      ))}
    </ul>
  );
}

/** The head's side column: the product shot where the page has one, else what's on the page. */
function HeadAside({ page }: { page: GtmPage }) {
  const shot = page.shot ? SHOTS[page.shot] : null;
  if (shot) {
    return (
      <figure className={`pp-shot pp-shot-${page.shot}`}>
        <Image
          src={shot.src}
          width={shot.width}
          height={shot.height}
          alt={shot.alt}
          priority
          sizes="(min-width: 1060px) 560px, calc(100vw - 2rem)"
        />
        <figcaption>The {SITE_NAME} app with example data. The shop, people and messages are made up.</figcaption>
      </figure>
    );
  }
  const checked = legalDate(latestChecked(page));
  const links = [
    ...page.blocks.map((block) => ({ href: `#${block.id}`, label: block.title })),
    ...(page.compare ? [{ href: `#${SIDE_BY_SIDE}`, label: "Side by side" }] : []),
    { href: `#${BEFORE_YOU_DECIDE}`, label: "What to know before you decide" },
  ];
  return (
    <nav className="pp-toc" aria-label="On this page">
      <p className="pp-toc-h">On this page</p>
      <ul>
        {links.map((link) => (
          <li key={link.href}>
            <a href={link.href}>{link.label}</a>
          </li>
        ))}
      </ul>
      {checked ? <p className="pp-toc-foot">Sources read on {checked}</p> : null}
    </nav>
  );
}

/**
 * A go-to-market page (GR-37; C-159 look): the head with one h1 beside the product shot or an "on
 * this page" card, the content blocks as h2 sections of icon cards (on a comparison, "Which fits
 * you" as two verdict cards), the site's three setup steps on a feature page, the side-by-side table,
 * what to know with the sources and the trademark note as a footnote card, related pages as linked
 * cards, and the closing call to action on a night band. The content is lib/marketing/gtm-pages.ts.
 */
export function GtmPageView({ page }: { page: GtmPage }) {
  const note = competitorNote(page);
  const feature = page.path.startsWith("/features/");
  return (
    <main id="main" tabIndex={-1} className="pp flex-1 outline-none">
      {/* A comparison sits under the /compare hub (C-156): Home, Compare, the page. */}
      {page.path.startsWith(`${COMPARE_PATH}/`) ? (
        <JsonLd
          data={breadcrumbTrailJsonLd([
            { name: "Compare", path: COMPARE_PATH },
            { name: page.name, path: page.path },
          ])}
        />
      ) : (
        <BreadcrumbJsonLd name={page.name} path={page.path} />
      )}
      <section className="page-head pp-head">
        <div className={page.shot ? "wrap pp-head-grid has-shot" : "wrap pp-head-grid"}>
          <div>
            <p className={SECTION_EYEBROW}>{page.eyebrow}</p>
            <h1 className="h-page">{page.h1}</h1>
            <p className="lede">{page.intro}</p>
            <div className="ctas pp-ctas">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={PRICING_PATH} variant="secondary">
                See plans and limits
              </CtaLink>
            </div>
          </div>
          <HeadAside page={page} />
        </div>
      </section>

      {page.blocks.map((block) => (
        <section key={block.id} id={block.id} aria-labelledby={`${block.id}-title`} className="band scroll-mt-24">
          <div className="wrap">
            <div className={block.intro ? "split-head" : undefined}>
              <h2 id={`${block.id}-title`} className="h-sec">
                {block.title}
              </h2>
              {block.intro ? <p className="lede">{block.intro}</p> : null}
            </div>
            {block.id === "choose" ? <Verdict block={block} /> : <Cards block={block} />}
          </div>
        </section>
      ))}

      {feature ? (
        <section aria-labelledby="setup-title" className="band pp-steps">
          <div className="wrap">
            <h2 id="setup-title" className="h-sec">
              Set up in three steps
            </h2>
            <ol className="steps after-head">
              {SETUP_STEPS.map((step) => (
                <li key={step.title}>
                  <h3>
                    <Ico icon={step.icon} />
                    {step.title}
                  </h3>
                  <p>{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>
      ) : null}

      <Compare page={page} />

      <section id={BEFORE_YOU_DECIDE} aria-labelledby="checked-title" className="band scroll-mt-24">
        <div className="wrap">
          <h2 id="checked-title" className="h-sec">
            What to know before you decide
          </h2>
          <div className={page.sources.length > 0 ? "know after-head" : "know is-single after-head"}>
            <div className="pp-callout">
              <Ico icon={Info} />
              <ul>
                {page.honesty.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            {page.sources.length > 0 ? (
              <div className="fnote">
                <h3>Sources</h3>
                <ul aria-label="Sources">
                  {page.sources.map((source) => (
                    <li key={source.url}>
                      <a href={source.url} rel="noopener noreferrer" className="tlink">
                        {source.label}
                      </a>{" "}
                      <span>(read {legalDate(source.checked) ?? source.checked})</span>
                    </li>
                  ))}
                </ul>
                {note ? (
                  <p className="fnote-tm">
                    {note.text}{" "}
                    <a href={`mailto:${note.email}`} className="tlink">
                      {note.email}
                    </a>
                    .
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <RelatedCards links={page.related} />
      <FinalCta />
    </main>
  );
}

/** "Keep reading" (C-159): each related page as a linked card with an arrow; mail links stay plain anchors. */
export function RelatedCards({ links }: { links: readonly { label: string; href: string }[] }) {
  return (
    <section aria-labelledby="related-title" className="band pp-related">
      <div className="wrap">
        <h2 id="related-title" className="h-sec">
          Keep reading
        </h2>
        <ul className="rcards after-head">
          {links.map((link) => (
            <li key={link.href}>
              {link.href.startsWith("mailto:") ? (
                <a href={link.href} className="rcard">
                  <span>{link.label}</span>
                  <ArrowRight className="size-4" aria-hidden />
                </a>
              ) : (
                <Link href={link.href as Route} className="rcard">
                  <span>{link.label}</span>
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
              )}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
