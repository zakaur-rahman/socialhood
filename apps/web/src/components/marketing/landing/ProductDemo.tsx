import { AlertTriangle, Check, CornerDownLeft, LoaderCircle, MousePointer2, RefreshCw, SendHorizontal, Sparkles, X, Zap } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { PLATFORM_LOGO_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { MotionToggle } from "@/components/site/MotionToggle";
import type { Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";

import { DM_SCRIPT, DEFAULT_KEYWORD, SOURCES } from "./data";

/*
 * C-175: the inbox at work, played as one story. The words and layout are the app's own, recreated as
 * markup (no app component on the marketing page): ConversationRow and rowBadges (the row, "You: ",
 * "Automation: ", "Lead 72/100", "Needs you", "Auto replies"), ThreadHeader ("AI: Suggest", "Window: 23h
 * left", "Needs you: asked for a person"), AnalysisChips (intent and sentiment), SuggestionCard ("AI
 * draft:", "From: Price list", Draft again, Insert, Send), MessageBubble (the quick reply, "Automation ·
 * …", the status icons), lib/ai/format.ts escalationBanner, and services/automations/actions.py (tap
 * first). docs/CONFLICTS.md C-175 lists where the story simplifies the product.
 */

export const PRODUCT_DEMO_ID = "product-demo";
export const PRODUCT_DEMO_TITLE = "See a day in your inbox";
export const PRODUCT_DEMO_NOTE = "Example, with made-up data";

export const PRODUCT_DEMO_STEPS = [
  "A DM arrives",
  "The AI reads it",
  "It drafts from your knowledge",
  "You stay in control",
  "A comment becomes a DM",
  "The tricky one comes to you",
];

/** What the scene shows, for screen readers (the scene itself is a picture, and it moves). */
export const PRODUCT_DEMO_LABEL = `Example: a new Instagram message arrives in an inbox that also holds WhatsApp and website chat. The AI tags its intent and lead score, then drafts a reply from the shop's price list. You press Send, and the conversation shows your reply. Next, someone comments ${DEFAULT_KEYWORD} on a Reel: an automation opens a DM with a button, and sends the link once they tap it. Then a customer on WhatsApp asks to talk to a person: the AI doesn't reply, and the conversation is marked Needs you.`;

const QUESTION = "Is the linen shirt in M?";
const DRAFT = "Yes, the linen shirt comes in S to XL, for $39. Shall I send you the order link?";
const OPENER = DM_SCRIPT.opener;
const LINK_LINE = "Here's the new linen collection.";
const AUTOMATION = "Linen Reel";
const PERSON = "Can I talk to a person?";

/** Each moving part has a name (`data-p`), which landing-motion.ts's timeline turns on and off. */
const part = (name: string) => ({ "data-p": name });

function Avatar({ name, shade, platform }: { name: string; shade: number; platform?: Platform }) {
  return (
    <span className="av pd-av" style={{ "--bg": `var(--av-${shade})` } as CSSProperties}>
      {name.charAt(0).toUpperCase()}
      {platform ? (
        <span className={`pd-mark ${PLATFORM_LOGO_BG[platform]}`}>
          <PlatformGlyph platform={platform} />
        </span>
      ) : null}
    </span>
  );
}

function Row({ id, slot, name, shade, platform, ago, children, badges }: { id: string; slot: number; name: string; shade: number; platform: Platform; ago: string; children: ReactNode; badges?: ReactNode }) {
  return (
    <li className="pd-row" data-row={id} {...part(`row-${id}`)} style={{ "--slot": slot } as CSSProperties}>
      <span className="pd-sel pd-before" {...part(`sel-${id}`)} />
      <Avatar name={name} shade={shade} platform={platform} />
      <span className="pd-row-main">
        <span className="pd-row-top">
          <b>{name}</b>
          <time className="num">{ago}</time>
        </span>
        <span className="pd-swap pd-row-text">{children}</span>
        {badges ? <span className="pd-badges">{badges}</span> : null}
      </span>
    </li>
  );
}

function Conversation({ id, name, handle, shade, platform, ai, needsYou, window: windowLeft, first, children }: { id: string; name: string; handle?: string; shade: number; platform: Platform; ai: string; needsYou?: boolean; window?: boolean; first?: boolean; children: ReactNode }) {
  return (
    <div className={first ? "pd-conv pd-first" : "pd-conv"} {...part(`conv-${id}`)}>
      <div className="pd-head">
        <Avatar name={name} shade={shade} platform={platform} />
        <span className="pd-who">
          <span className="pd-who-top">
            <b>{name}</b>
            {windowLeft ? <span className="tag t-plain pd-window">Window: 23h left</span> : null}
            {needsYou ? (
              <span className="tag t-need" {...part(`${id}-need`)}>
                Needs you: asked for a person
              </span>
            ) : null}
          </span>
          <span className="pd-id">
            {handle ? `${handle} · ` : ""}
            <PlatformGlyph platform={platform} className={`pd-glyph pd-c-${platform}`} />
            {PLATFORM_LABEL[platform]}
          </span>
        </span>
        <span className="tag t-draft pd-mode">{ai}</span>
      </div>
      <div className="pd-log">{children}</div>
      <div className="pd-composer">
        <span>Reply to {name.split(/[\s.]/)[0]}…</span>
        <span className="pd-send-empty">
          Send <SendHorizontal className="size-3.5" aria-hidden />
        </span>
      </div>
    </div>
  );
}

function Meta({ automation, children }: { automation?: boolean; children?: ReactNode }) {
  return (
    <p className="pd-meta num">
      10:42 AM
      {children}
      {automation ? (
        <span className="pd-by">
          <Zap className="size-3" aria-hidden />
          Automation · {AUTOMATION}
        </span>
      ) : null}
    </p>
  );
}

function MayaThread() {
  return (
    <Conversation id="maya" name="Maya R." handle="@maya.r" shade={2} platform="instagram" ai="AI: Suggest" window first>
      <div className="pd-in">
        <p className="pd-bub">{QUESTION}</p>
        <p className="pd-chips" {...part("maya-tags")}>
          <span className="tag t-draft">Product question</span>
          <span className="tag t-plain">
            <i className="pd-dot" />
            Neutral
          </span>
        </p>
      </div>
      <div className="pd-cell">
        <div className="pd-bar" {...part("maya-bar")}>
          <div className="pd-bar-top">
            <Sparkles className="pd-spark size-3.5" aria-hidden />
            <div className="pd-swap pd-draft">
              <p className="pd-drafting pd-before" {...part("maya-drafting")}>
                <b>AI draft:</b> Drafting a reply…
              </p>
              <p className="pd-words" {...part("maya-words")}>
                <b>AI draft: </b>
                {DRAFT.split(" ").map((word, i) => (
                  <span key={i} className="w" style={{ "--n": i } as CSSProperties}>
                    {word}{" "}
                  </span>
                ))}
              </p>
            </div>
            <X className="pd-x size-3.5" aria-hidden />
          </div>
          <div className="pd-bar-foot" {...part("maya-source")}>
            <span className="tag t-plain">From: Price list</span>
            <span className="pd-acts">
              <span className="pd-act pd-act-far">
                <RefreshCw className="size-3.5" aria-hidden /> Draft again
              </span>
              <span className="pd-act pd-act-line">
                <CornerDownLeft className="size-3.5" aria-hidden /> Insert
              </span>
              <span className="pd-act pd-act-main">
                <SendHorizontal className="size-3.5" aria-hidden /> Send
                <span className="pd-click pd-before" {...part("maya-click")} />
                <MousePointer2 className="pd-cursor pd-before" {...part("maya-cursor")} aria-hidden />
              </span>
            </span>
          </div>
        </div>
        <div className="pd-out" {...part("maya-out")}>
          <p className="pd-bub">{DRAFT}</p>
          <Meta>
            <span className="pd-swap pd-status">
              <LoaderCircle className="size-3.5 pd-before" {...part("maya-sending")} aria-hidden />
              <Check className="size-3.5" {...part("maya-sent")} aria-hidden />
            </span>
          </Meta>
        </div>
      </div>
    </Conversation>
  );
}

function AnaThread() {
  return (
    <Conversation id="ana" name="ana.wears" handle="@ana.wears" shade={5} platform="instagram" ai="AI: Suggest" window>
      <p className="pd-comment" {...part("ana-comment")}>
        <PlatformGlyph platform="instagram" className="pd-glyph pd-c-instagram" />
        <span>{SOURCES.comment.label}</span>
        <b>ana.wears</b>
        <mark>{DEFAULT_KEYWORD}</mark>
      </p>
      <div className="pd-out" {...part("ana-open")}>
        <div className="pd-bub">
          {OPENER}
          <span className="pd-quick">{DM_SCRIPT.button}</span>
        </div>
        <Meta automation />
      </div>
      <div className="pd-in" {...part("ana-tap")}>
        <p className="pd-bub">{DM_SCRIPT.button}</p>
      </div>
      <div className="pd-out" {...part("ana-link")}>
        <div className="pd-bub">
          {LINK_LINE}
          <span className="pd-url">indigolane.example/linen</span>
        </div>
        <Meta automation />
      </div>
    </Conversation>
  );
}

function SamThread() {
  return (
    <Conversation id="sam" name="Sam K." shade={4} platform="whatsapp" ai="AI: Auto" needsYou window>
      <div className="pd-in">
        <p className="pd-bub">{PERSON}</p>
      </div>
      <p className="pd-banner" {...part("sam-banner")}>
        <AlertTriangle className="size-4" aria-hidden />
        AI didn&apos;t reply: customer asked for a person
      </p>
    </Conversation>
  );
}

/**
 * "See a day in your inbox" (C-175), between the hero and How it works: one app window, an inbox list
 * and the open conversation, plays one story about 21 s long and rests before it loops
 * (landing-motion.ts, productDemo; only opacity and transform move, and every box keeps its size).
 * Under the frame, the story's steps as plain captions, and its pause control (MotionToggle).
 * With no script, or `prefers-reduced-motion`, site.css lays the three conversations out one under
 * the other, finished, and nothing moves. The scene is one labelled picture for assistive tech.
 */
export function ProductDemo() {
  return (
    <section className="sec sec-tight pd" id={PRODUCT_DEMO_ID} aria-labelledby="product-demo-title" data-motion-scope="">
      <div className="wrap">
        <div className="split-head">
          <h2 id="product-demo-title" className="h2">
            {PRODUCT_DEMO_TITLE}
          </h2>
          <p className="lede">
            Messages from each channel land in one list. The AI reads them, drafts from your knowledge and hands you the ones it
            shouldn&apos;t answer.
          </p>
        </div>
        <figure className="pd-stage after-head" data-demo="">
          <div className="pd-win" data-ui="" role="img" aria-label={PRODUCT_DEMO_LABEL}>
            <div className="mh-bar" aria-hidden>
              <span className="mh-dots">
                <i />
                <i />
                <i />
              </span>
              <b>Inbox</b>
            </div>
            <div className="pd-body" aria-hidden>
              <div className="pd-list">
                <div className="pd-list-h">
                  <span className="pd-chip pd-chip-on">All</span>
                  <span className="pd-chip">Unread</span>
                  <span className="pd-chip">
                    Needs you
                    <b className="num" {...part("need-count")}>
                      1
                    </b>
                  </span>
                </div>
                <ol className="pd-rows">
                  <Row id="sam" slot={0} name="Sam K." shade={4} platform="whatsapp" ago="now" badges={
                    <>
                      <span className="tag t-need" {...part("sam-row-need")}>Needs you</span>
                      <span className="tag t-plain" {...part("sam-row-auto")}>Auto replies</span>
                    </>
                  }>
                    <span>{PERSON}</span>
                  </Row>
                  <Row id="ana" slot={1} name="ana.wears" shade={5} platform="instagram" ago="now">
                    <span className="pd-before" {...part("ana-row-open")}>Automation: {OPENER}</span>
                    <span {...part("ana-row-link")}>Automation: {LINK_LINE}</span>
                  </Row>
                  <Row id="maya" slot={2} name="Maya R." shade={2} platform="instagram" ago="now" badges={
                    <span className="tag t-draft" {...part("maya-lead")}>Lead 72/100</span>
                  }>
                    <span className="pd-before" {...part("maya-row-q")}>
                      {QUESTION}
                    </span>
                    <span {...part("maya-row-you")}>You: {DRAFT}</span>
                  </Row>
                  <Row id="nina" slot={3} name="Nina" shade={3} platform="whatsapp" ago="26m">
                    <span>What time do you open on Sunday?</span>
                  </Row>
                  <Row id="visitor" slot={4} name="Visitor" shade={1} platform="web" ago="41m">
                    <span>Do you take bulk orders?</span>
                  </Row>
                </ol>
              </div>
              <div className="pd-panes">
                <p className="pd-pick pd-before" {...part("pick")}>
                  Pick a conversation
                </p>
                <MayaThread />
                <AnaThread />
                <SamThread />
              </div>
            </div>
          </div>
          <figcaption className="stage-cap pd-cap">
            {PRODUCT_DEMO_NOTE}
            <MotionToggle label="Pause the example" />
          </figcaption>
        </figure>
        <ol className="pd-steps" data-demo-steps="">
          {PRODUCT_DEMO_STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>
    </section>
  );
}
