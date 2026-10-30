import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { MotionToggle } from "@/components/site/MotionToggle";
import { SECTION_IDS, SIGN_UP_PATH, SITE_TAGLINE, appUrl } from "@/lib/marketing/site";

import { CtaLink } from "../primitives";
import { CHANNELS, HERO_NOTES, HERO_PILE, SOURCES } from "./data";
import { Strip } from "./Strip";

import { HERO_AUDIENCE, HERO_LINE, HERO_TITLE } from "./copy";

export { HERO_LINE, HERO_TITLE };

/** The trust row under the calls to action: both true by construction (the official APIs, Free's terms). */
export const HERO_FACTS = ["Official Meta APIs", "Free plan, no card needed"];

/** A message's place in the scattered pile (HERO_PILE), for site.css: its row, offset and tilt. */
function pile(i: number): CSSProperties {
  const { x, y, r } = HERO_PILE[i % HERO_PILE.length];
  return { "--i": i, "--sx": x, "--sy": y, "--sr": r } as CSSProperties;
}

const need = HERO_NOTES.filter((note) => note.tone === "need").length;
const drafts = HERO_NOTES.filter((note) => note.tone === "draft").length;

/** What the scene shows, for screen readers (the scene itself is a picture). */
export const HERO_SCENE_LABEL = `Example: ${HERO_NOTES.length} messages from Instagram DMs and comments, WhatsApp and a website chat land in one inbox, sorted so the ${need} that need a person come first.`;

/**
 * The first screen (C-155, C-157): the headline, who it is for, the two ways in, and the inbox. The
 * owner's scene (C-157 motion): the messages start as a scattered pile and organize into the sorted
 * inbox. The server draws the pile itself (site.css, from HERO_PILE), so nothing jumps when the script
 * arrives, and the headline (the page's largest paint) never moves.
 * - A wide screen with a mouse: the frame pins and the scroll sorts the pile (a CSS scroll timeline;
 *   landing-motion.ts drives the same animations where the browser has none).
 * - A phone or a tablet: it sorts by itself once (1.2 s) when the inbox is on screen, with a pause
 *   control, then holds.
 * - No script, or `prefers-reduced-motion`: the sorted inbox, still.
 * The strip (the product in numbers) closes the section, after the pinned box. On a wide screen tall
 * enough to hold it, site.css lays it over the pinned frame's foot, so the first screen is complete;
 * everywhere else it simply follows the hero, as it always has (C-157 hero spacing).
 */
export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-scrub" data-hero-scrub="">
        <div className="hero-sticky">
          <div className="wrap hero-grid">
            <div className="hero-copy">
              <p className="hero-tag">
                <span className="chan-dots" aria-hidden>
                  {CHANNELS.map((key) => (
                    <i key={key} style={{ "--c": SOURCES[key].colour } as CSSProperties} />
                  ))}
                </span>
                {SITE_TAGLINE}
              </p>
              <h1 id="hero-title" className="h1">
                <span className="phrase">Every DM.</span> <span className="phrase">Every comment.</span> <em>One inbox.</em>
              </h1>
              <p className="hero-sub">
                <b>{HERO_AUDIENCE}</b> {HERO_LINE}
              </p>
              <div className="ctas hero-ctas">
                <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
                  Start free <ArrowRight className="size-4" aria-hidden />
                </CtaLink>
                <CtaLink href={`#${SECTION_IDS.howItWorks}`} variant="secondary">
                  See how it works
                </CtaLink>
              </div>
              <ul className="facts" aria-label="At a glance">
                {HERO_FACTS.map((fact) => (
                  <li key={fact}>
                    <Check className="size-4" strokeWidth={2.4} aria-hidden />
                    {fact}
                  </li>
                ))}
              </ul>
            </div>

            <figure className="stage" data-stage="" data-motion-scope="">
              <div className="inbox" data-inbox="" data-ui="" role="img" aria-label={HERO_SCENE_LABEL}>
                <span className="inbox-frame" aria-hidden>
                  <span className="chan-line">
                    {CHANNELS.map((key) => (
                      <i key={key} style={{ "--c": SOURCES[key].colour } as CSSProperties} />
                    ))}
                  </span>
                </span>
                <div className="panel-h">
                  <b>Inbox</b>
                  <span className="num">{HERO_NOTES.length} conversations</span>
                  <span className="chips">
                    <span className="tag t-need">{need} need you</span>
                    <span className="tag t-draft">{drafts} AI drafts</span>
                  </span>
                </div>
                <ol className="notes" data-notes="">
                  {HERO_NOTES.map((note, i) => (
                    <li key={note.name + note.text} className="note" style={pile(i)}>
                      <span className={note.source === "comment" ? "app app-ring" : "app"} style={{ "--c": SOURCES[note.source].colour } as CSSProperties}>
                        <i />
                        {SOURCES[note.source].label}
                      </span>
                      <span className="time num">{note.ago}</span>
                      <span className="note-main">
                        <b>{note.name}</b>
                        <span>{note.text}</span>
                      </span>
                      <span className={`tag t-${note.tone}`}>{note.tag}</span>
                    </li>
                  ))}
                </ol>
              </div>
              <figcaption className="stage-cap" data-ui="">
                Example data
                <MotionToggle label="Pause the inbox animation" className="stage-toggle" />
              </figcaption>
            </figure>
          </div>
        </div>
      </div>
      <Strip />
    </section>
  );
}
