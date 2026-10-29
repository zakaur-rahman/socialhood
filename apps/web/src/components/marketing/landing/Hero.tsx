import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { SECTION_IDS, SIGN_UP_PATH, SITE_TAGLINE, appUrl } from "@/lib/marketing/site";

import { CtaLink } from "../primitives";
import { HERO_NOTES, SOURCES } from "./data";

import { HERO_LINE, HERO_TITLE } from "./copy";

export { HERO_LINE, HERO_TITLE };

export const HERO_FACTS = ["Official Meta APIs", "Free plan, no card needed"];

const need = HERO_NOTES.filter((note) => note.tone === "need").length;
const drafts = HERO_NOTES.filter((note) => note.tone === "draft").length;

/** What the scene shows, for screen readers (the scene itself is a picture). */
export const HERO_SCENE_LABEL = `Example: ${HERO_NOTES.length} messages from Instagram DMs and comments, WhatsApp and a website chat land in one inbox, sorted so the ${need} that need a person come first.`;

/**
 * The first screen (C-155): the headline, the two ways in, and the scene, a pile of messages from
 * every channel that sorts itself into one inbox as you scroll (on phones it plays by itself). The
 * server renders the sorted inbox, so the scene means something with no script and nothing moves
 * when the script arrives (landing-motion.ts animates with transforms only).
 */
export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-scrub" data-hero-scrub="">
        <div className="hero-sticky">
          <div className="wrap hero-grid">
            <div className="hero-copy">
              <p className="eyebrow">
                <span className="dots" aria-hidden>
                  {(["dm", "comment", "whatsapp", "web"] as const).map((key) => (
                    <i key={key} style={{ "--c": SOURCES[key].colour } as CSSProperties} />
                  ))}
                </span>
                {SITE_TAGLINE}
              </p>
              <h1 id="hero-title" className="h1">
                <span className="phrase">Every DM.</span> <span className="phrase">Every comment.</span> <em>One inbox.</em>
              </h1>
              <p className="hero-sub">{HERO_LINE}</p>
              <div className="ctas">
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
              <div className="scroll-hint" data-hint="" aria-hidden>
                <span className="track" />
                <span data-hint-text="">Scroll to sort the inbox</span>
              </div>
            </div>

            <div className="stage" data-stage="" role="img" aria-label={HERO_SCENE_LABEL}>
              <div className="layer" data-layer="">
                <div className="inbox" data-inbox="">
                  <div className="panel" data-panel="" />
                  <div className="panel-h" data-panel-h="">
                    <b>Inbox</b>
                    <span className="num">{HERO_NOTES.length} conversations</span>
                    <span className="chips">
                      <span className="tag t-need">{need} need you</span>
                      <span className="tag t-draft">{drafts} AI drafts</span>
                    </span>
                  </div>
                  <ol className="notes">
                    {HERO_NOTES.map((note) => (
                      <li key={note.name + note.text} className="note">
                        <div className="note-in">
                          <div className="note-top">
                            <span className="app" style={{ "--c": SOURCES[note.source].colour } as CSSProperties}>
                              <i />
                              {SOURCES[note.source].label}
                            </span>
                            <span className="time num" aria-hidden>{note.ago}</span>
                          </div>
                          <div className="note-main">
                            <b>{note.name}</b>
                            <span>{note.text}</span>
                          </div>
                          <span className={`tag t-${note.tone}`}>{note.tag}</span>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
              <p className="stage-cap">
                <span className="capbox">
                  <span data-cap-a="" style={{ opacity: 0 }}>
                    Every DM. Every comment.
                  </span>
                  <span data-cap-b="">One inbox. Example data.</span>
                </span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
