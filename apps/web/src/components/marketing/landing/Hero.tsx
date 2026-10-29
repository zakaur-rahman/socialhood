import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { SECTION_IDS, SIGN_UP_PATH, SITE_TAGLINE, appUrl } from "@/lib/marketing/site";

import { CtaLink } from "../primitives";
import { CHANNELS, HERO_NOTES, SOURCES } from "./data";

import { HERO_AUDIENCE, HERO_LINE, HERO_TITLE } from "./copy";

export { HERO_LINE, HERO_TITLE };

/** The trust row under the calls to action: both true by construction (the official APIs, Free's terms). */
export const HERO_FACTS = ["Official Meta APIs", "Free plan, no card needed"];

const need = HERO_NOTES.filter((note) => note.tone === "need").length;
const drafts = HERO_NOTES.filter((note) => note.tone === "draft").length;

/** What the scene shows, for screen readers (the scene itself is a picture). */
export const HERO_SCENE_LABEL = `Example: ${HERO_NOTES.length} messages from Instagram DMs and comments, WhatsApp and a website chat land in one inbox, sorted so the ${need} that need a person come first.`;

/**
 * The first screen (C-155, reworked C-157): the headline, who it is for, the two ways in, and the
 * inbox, server-rendered already sorted, so the first frame means something with or without script.
 * Once the page is idle, landing-motion.ts plays one short sort (a new message lands on top and
 * moves to its place, about a second, transforms only) and holds. The headline is the page's
 * largest paint and never moves.
 */
export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
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

        <figure className="stage" data-stage="">
          <div className="inbox" data-inbox="" data-ui="" role="img" aria-label={HERO_SCENE_LABEL}>
            <span className="chan-line">
              {CHANNELS.map((key) => (
                <i key={key} style={{ "--c": SOURCES[key].colour } as CSSProperties} />
              ))}
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
              {HERO_NOTES.map((note) => (
                <li key={note.name + note.text} className="note" data-arrives={note.arrives ? "" : undefined}>
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
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
