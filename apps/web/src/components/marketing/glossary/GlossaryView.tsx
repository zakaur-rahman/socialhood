import { ArrowLeft, ArrowRight, BookOpenText, CalendarCheck, ExternalLink, MessagesSquare, Radio } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { StatusChip } from "@/components/site/StatusChip";
import { legalDate } from "@/lib/legal";
import {
  GLOSSARY,
  GLOSSARY_PATH,
  findTerm,
  glossaryByLetter,
  glossaryPath,
  termChecked,
  type GlossaryChannel,
  type GlossaryTerm,
} from "@/lib/marketing/glossary";
import { GLOSSARY_NAME, definedTermJsonLd, definedTermSetJsonLd } from "@/lib/marketing/glossary-seo";
import { breadcrumbJsonLd, breadcrumbTrailJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { FinalCta } from "../FinalCta";
import { JsonLd } from "../JsonLd";
import { Ico } from "../landing/Ico";
import { CtaLink, SECTION_EYEBROW } from "../primitives";
import { GlossaryFilter } from "./GlossaryFilter";

const LIST_ID = "glossary-list";
const LETTERS = ["#", ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"];

function letterId(letter: string): string {
  return letter === "#" ? "terms-0-9" : `terms-${letter.toLowerCase()}`;
}

/** A term's channel as its mark: the channel's own glyph in its colour, or a speech icon for both. */
export function ChannelMark({ channel }: { channel: GlossaryChannel }) {
  if (channel === "Meta") return <Ico icon={MessagesSquare} />;
  const platform = channel === "WhatsApp" ? "whatsapp" : "instagram";
  return (
    <Ico className="ico-mark" style={{ "--c": platform === "whatsapp" ? "var(--wa)" : "var(--ig)" } as CSSProperties}>
      <PlatformGlyph platform={platform} />
    </Ico>
  );
}

/** "WhatsApp", "Instagram", or "WhatsApp and Instagram" for a term that covers both. */
export function channelLabel(channel: GlossaryChannel): string {
  return channel === "Meta" ? "WhatsApp and Instagram" : channel;
}

/**
 * The glossary index (C-163): a split head, a bar with the A–Z links and the search and channel
 * filter (a client island in a reserved slot; without script the list is complete and the letters
 * still jump), the terms grouped by letter as cards with their one-sentence definition, how the
 * glossary is written, and the night close. DefinedTermSet and breadcrumbs JSON-LD.
 */
export function GlossaryIndex() {
  const groups = glossaryByLetter();
  const present = new Set(groups.map((group) => group.letter));
  const checked = legalDate(GLOSSARY.map(termChecked).sort().at(-1));
  return (
    <main id="main" tabIndex={-1} className="pp gloss flex-1 outline-none">
      <JsonLd data={breadcrumbJsonLd("Glossary", GLOSSARY_PATH)} />
      <JsonLd data={definedTermSetJsonLd()} />
      <section className="page-head gl-head">
        <div className="wrap split-head">
          <div>
            <p className={SECTION_EYEBROW}>Glossary</p>
            <h1 className="h-page">{GLOSSARY_NAME}</h1>
          </div>
          <div>
            <p className="lede">
              The WhatsApp, Instagram and Messenger terms you meet when you message customers, each in one plain sentence, with
              Meta&apos;s own sources and how Amplychat handles it.
            </p>
            {checked ? (
              <p className="gl-meta">
                <CalendarCheck size={16} strokeWidth={1.75} aria-hidden focusable="false" /> {GLOSSARY.length} terms · Meta&apos;s
                docs read on {checked}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      <div data-glossary="">
        <div className="gl-bar">
          <div className="wrap gl-bar-in">
            <nav aria-label="Terms by letter" className="gl-az">
              <ul>
                {LETTERS.map((letter) => (
                  <li key={letter}>
                    {present.has(letter) ? (
                      <a href={`#${letterId(letter)}`} data-letter-link={letter} aria-label={letter === "#" ? "Numbers" : `Letter ${letter}`}>
                        {letter}
                      </a>
                    ) : (
                      <span aria-hidden>{letter}</span>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
            <div className="gl-filter">
              <GlossaryFilter listId={LIST_ID} total={GLOSSARY.length} />
            </div>
          </div>
        </div>

        <section aria-labelledby="gl-list-title" className="band gl-list">
          <div className="wrap">
            <h2 id="gl-list-title" className="sr-only">
              All terms
            </h2>
            <div id={LIST_ID}>
              {groups.map((group) => (
                <section key={group.letter} id={letterId(group.letter)} data-letter={group.letter} aria-labelledby={`${letterId(group.letter)}-h`} className="gl-group">
                  <h3 id={`${letterId(group.letter)}-h`} className="gl-letter">
                    {group.letter === "#" ? <span aria-label="Numbers">0–9</span> : group.letter}
                  </h3>
                  <ul className="gl-cards">
                    {group.terms.map((term) => (
                      <li
                        key={term.slug}
                        data-term=""
                        data-channel={term.channel}
                        data-text={[term.term, ...(term.aka ?? []), term.definition].join(" ")}
                      >
                        <article className="gl-card">
                          <ChannelMark channel={term.channel} />
                          <div className="gl-card-h">
                            <h4 className="gl-card-t">
                              {/* The whole row is the link's target; the term is its name. */}
                              <Link href={glossaryPath(term.slug) as Route}>{term.term}</Link>
                            </h4>
                            <span className="gl-chan-t">{channelLabel(term.channel)}</span>
                          </div>
                          <p>{term.definition}</p>
                          <ArrowRight className="gl-card-go size-4" aria-hidden />
                        </article>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </div>
        </section>
      </div>

      <section aria-labelledby="gl-how-title" className="band">
        <div className="wrap gl-how">
          <h2 id="gl-how-title" className="h-sec">
            How we write these
          </h2>
          <ul className="gcards is-3 after-head">
            <li className="gcard is-plain">
              <Ico icon={BookOpenText} />
              <p>Every rule comes from Meta&apos;s own documentation, listed on the term&apos;s page with the date we read it.</p>
            </li>
            <li className="gcard is-plain">
              <Ico icon={Radio} />
              <p>&ldquo;How Amplychat handles it&rdquo; is checked against our own code, with what waits on Meta marked as such.</p>
            </li>
            <li className="gcard is-plain">
              <Ico icon={CalendarCheck} />
              <p>Meta changes its rules and prices, so check the linked page before you rely on a detail.</p>
            </li>
          </ul>
        </div>
      </section>
      <FinalCta />
    </main>
  );
}

/** A term's sources, each with the date read and how. */
function Sources({ term }: { term: GlossaryTerm }) {
  const viaSearch = term.sources.some((source) => source.via === "search");
  return (
    <div className="fnote gl-sources">
      <h3>Meta&apos;s sources</h3>
      <ul aria-label="Sources">
        {term.sources.map((source) => (
          <li key={source.url}>
            <a href={source.url} rel="noopener noreferrer" className="tlink">
              {source.label}
              <ExternalLink size={13} strokeWidth={1.75} aria-hidden focusable="false" />
            </a>{" "}
            <span>
              (read {legalDate(source.checked)}
              {source.via === "search" ? ", through a search engine's copy" : ""})
            </span>
          </li>
        ))}
      </ul>
      {viaSearch ? (
        <p className="fnote-tm">Meta&apos;s help centres don&apos;t answer automated reads, so those pages were read through a search engine&apos;s copy.</p>
      ) : null}
    </div>
  );
}

/**
 * One term (C-163): the back link, the eyebrow with its channel, the term as the h1 and its
 * one-sentence definition as the lede; then, from 1060 px, the detail, "How Amplychat handles it"
 * (status cards) and related terms beside a sticky side column with the facts, the sources and the
 * page to read next; then the night close. DefinedTerm (in the set) and breadcrumbs JSON-LD.
 */
export function TermView({ term }: { term: GlossaryTerm }) {
  const path = glossaryPath(term.slug);
  const related = term.related.map((slug) => findTerm(slug)).filter((item): item is GlossaryTerm => Boolean(item));
  const checked = legalDate(termChecked(term));
  return (
    <main id="main" tabIndex={-1} className="pp gloss flex-1 outline-none">
      <JsonLd
        data={breadcrumbTrailJsonLd([
          { name: "Glossary", path: GLOSSARY_PATH },
          { name: term.term, path },
        ])}
      />
      <JsonLd data={definedTermJsonLd(term)} />
      <article aria-labelledby="term-title">
        <header className="page-head gl-thead">
          <div className="wrap">
            <Link href={GLOSSARY_PATH as Route} className="gl-back">
              <ArrowLeft size={16} strokeWidth={1.75} aria-hidden focusable="false" /> All terms
            </Link>
            <p className={SECTION_EYEBROW}>Glossary · {channelLabel(term.channel)}</p>
            <h1 id="term-title" className="h-page gl-h1">
              {term.term}
            </h1>
            <p className="lede gl-def" data-definition="">
              {term.definition}
            </p>
            {term.aka?.length ? (
              <p className="gl-aka">
                <span>Also called</span> {term.aka.join(", ")}
              </p>
            ) : null}
          </div>
        </header>

        <div className="wrap gl-grid">
          <div className="gl-main">
            <section aria-labelledby="detail-title" className="gl-sec">
              <h2 id="detail-title" className="gl-h2">
                What it means
              </h2>
              <div className="gl-prose">
                {term.detail.map((paragraph) => (
                  <p key={paragraph.slice(0, 40)}>{paragraph}</p>
                ))}
              </div>
            </section>

            <section aria-labelledby="handling-title" className="gl-sec">
              <h2 id="handling-title" className="gl-h2">
                How Amplychat handles it
              </h2>
              <ul className="gl-handle">
                {term.handling.map((item) => (
                  <li key={item.title} className="gl-hcard">
                    <StatusChip status={item.status} />
                    <h3>{item.title}</h3>
                    <p>{item.body}</p>
                  </li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="related-terms-title" className="gl-sec">
              <h2 id="related-terms-title" className="gl-h2">
                Related terms
              </h2>
              <ul className="hub gl-related">
                {related.map((item) => (
                  <li key={item.slug}>
                    <article className="hcard">
                      <h3>
                        <Link href={glossaryPath(item.slug) as Route} className="hcard-link">
                          {item.term}
                        </Link>
                        <ArrowRight className="hcard-arrow size-4" aria-hidden />
                      </h3>
                      <p>{item.definition}</p>
                    </article>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <aside className="gl-side" aria-label="About this term">
            <div className="gl-side-in">
              <dl className="gl-facts">
                <div>
                  <dt>Channel</dt>
                  <dd>
                    <ChannelMark channel={term.channel} /> {channelLabel(term.channel)}
                  </dd>
                </div>
                {checked ? (
                  <div>
                    <dt>Checked</dt>
                    <dd>
                      <time dateTime={termChecked(term)}>{checked}</time>
                    </dd>
                  </div>
                ) : null}
              </dl>
              <Sources term={term} />
              <Link href={term.learn.href as Route} className="rcard gl-learn">
                <span>{term.learn.label}</span>
                <ArrowRight className="size-4" aria-hidden />
              </Link>
              <div className="gl-try">
                <p className="gl-try-t">Try it on your own messages</p>
                <p>The Free plan needs no card.</p>
                <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="gl-try-btn">
                  Start free <ArrowRight className="size-4" aria-hidden />
                </CtaLink>
              </div>
            </div>
          </aside>
        </div>
      </article>
      <FinalCta />
    </main>
  );
}
