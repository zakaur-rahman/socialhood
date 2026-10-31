import { BookOpenText, Heart, Link2, Send } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { CommentMachine } from "@/components/marketing/landing/Comments";
import { SOURCES } from "@/components/marketing/landing/data";
import { HeroInbox } from "@/components/marketing/landing/Hero";
import { Ico } from "@/components/marketing/landing/Ico";
import { ModeSwitch } from "@/components/marketing/landing/Modes";
import type { AutomationScene } from "@/lib/marketing/automation-pages";

/**
 * The product scene under each automation page's head (C-163). The landing's own scenes where they
 * fit, imported and not copied (the comment-to-DM machine, the Off / Suggest / Auto switch, the hero
 * inbox on the hub); small card scenes in the same language elsewhere (the C-160 `.xs` parts, plus
 * the C-163 auto block). Every scene is server-rendered finished, its parts arrive once in order when it
 * first comes into view (`[data-xv]`, explainer-motion.ts), and it is captioned as example data.
 */

const k = (n: number) => ({ "--k": n }) as CSSProperties;
const mark = (colour: string) => ({ "--c": colour }) as CSSProperties;

function Scene({ className, label, children }: { className: string; label: string; children: ReactNode }) {
  return (
    <figure className={`xs ap-sc ${className}`} data-xv="">
      <div className="ap-sc-box" data-ui="" role="img" aria-label={label}>
        {children}
      </div>
      <figcaption className="cap">Example data</figcaption>
    </figure>
  );
}

function Who({ name, letter, avatar, source = "dm" }: { name: string; letter: string; avatar: number; source?: keyof typeof SOURCES }) {
  return (
    <div className="xs-msg">
      <span className="av" style={{ "--bg": `var(--av-${avatar})` } as CSSProperties}>
        {letter}
      </span>
      <span>
        <b>{name}</b>
        <span className="app" style={mark(SOURCES[source].colour)}>
          <i />
          {SOURCES[source].label}
        </span>
      </span>
    </div>
  );
}

function StoryScene() {
  return (
    <Scene className="ap-sc-story" label="Example: someone replies PINK to a Story; the automation sends a heart, then a message with a Remind me button.">
      <div className="ap-story xv-i" style={k(0)}>
        <span className="ap-story-top">
          <Ico className="ico-mark" style={mark("var(--ig)")}>
            <PlatformGlyph platform="instagram" />
          </Ico>
          Your Story
        </span>
        <b className="ap-story-t">The pink tote drops Friday</b>
        <span className="ap-story-ask">Reply PINK to get it first</span>
      </div>
      <div className="xs-card ap-thread">
        <Who name="Riya" letter="R" avatar={3} />
        <p className="ap-ctx xv-i" style={k(1)}>
          Replied to your story
        </p>
        <p className="xs-bub ap-in xv-i" style={k(1)}>
          PINK 💗
        </p>
        <p className="ap-heart xv-i" style={k(2)}>
          <Heart className="size-3.5" aria-hidden /> Heart sent
        </p>
        <p className="ap-out xv-i" style={k(3)}>
          You&apos;re on the list! Want a reminder on Friday?
          <span className="ap-btn">Remind me</span>
        </p>
      </div>
    </Scene>
  );
}

function KeywordScene() {
  return (
    <Scene className="ap-sc-kw" label="Example: a DM asking for the price matches the keyword PRICE as a whole word, and the automation replies with a price list button.">
      <div className="xs-card ap-thread">
        <Who name="Dev" letter="D" avatar={1} />
        <p className="xs-bub ap-in xv-i" style={k(0)}>
          hi! what&apos;s the <mark className="ap-hit">price</mark> for a 1 kg cake?
        </p>
        <p className="ap-out xv-i" style={k(2)}>
          Here&apos;s our full price list, with sizes and flavours.
          <span className="ap-btn">
            <Link2 className="size-3.5" aria-hidden /> See the price list
          </span>
        </p>
      </div>
      <div className="xs-card ap-rule xv-i" style={k(1)}>
        <p className="xs-h">
          <b>
            <Send className="size-4" aria-hidden /> Instagram DM keyword
          </b>
          <span className="tag t-ok">On</span>
        </p>
        <ul className="ap-chips" aria-label="Keywords">
          <li className="is-hit">PRICE</li>
          <li>MENU</li>
          <li>RATES</li>
        </ul>
        <dl className="ap-kv">
          <div>
            <dt>Match</dt>
            <dd>Whole word</dd>
          </div>
          <div>
            <dt>Cooldown</dt>
            <dd>24 hours</dd>
          </div>
          <div>
            <dt>Reply</dt>
            <dd>Message and a link</dd>
          </div>
        </dl>
      </div>
    </Scene>
  );
}

const STARTERS = ["See prices", "Book an appointment", "Where are you?", "Ask a question"];

function StartersScene() {
  return (
    <Scene className="ap-sc-starters" label="Example: a new chat shows four conversation starters; tapping Book an appointment gets an answer at once.">
      <div className="xs-card ap-phone">
        <div className="ap-phone-h">
          <span className="av" style={{ "--bg": "var(--av-5)" } as CSSProperties}>
            L
          </span>
          <span>
            <b>lane.salon</b>
            <small>New chat</small>
          </span>
        </div>
        <ul className="ap-starters">
          {STARTERS.map((question, index) => (
            <li key={question} className={index === 1 ? "xv-i is-tap" : "xv-i"} style={k(index)}>
              {question}
            </li>
          ))}
        </ul>
        <p className="ap-out ap-self xv-i" style={k(4)}>
          Book an appointment
        </p>
        <p className="xs-bub ap-in ap-them xv-i" style={k(5)}>
          Lovely! Which day suits you?
        </p>
      </div>
    </Scene>
  );
}

function WidgetScene() {
  return (
    <Scene className="ap-sc-widget" label="Example: a chat widget on a shop's product page answers a sizing question from the shop's knowledge.">
      <div className="ap-site" aria-hidden>
        <span className="ap-site-bar">
          <i />
          <i />
          <i />
          <span>yourshop.com/linen-shirt</span>
        </span>
        <span className="ap-site-body">
          <span className="ap-site-img" />
          <span className="ap-site-lines">
            <b>Linen shirt</b>
            <i />
            <i />
            <i />
          </span>
        </span>
      </div>
      <div className="xs-card ap-widget">
        <p className="ap-widget-h">
          <Ico className="ico-mark" style={mark("var(--web)")}>
            <PlatformGlyph platform="web" />
          </Ico>
          <b>Chat with us</b>
        </p>
        <p className="xs-bub ap-in ap-them xv-i" style={k(0)}>
          Hi! How can we help?
        </p>
        <p className="ap-out ap-self xv-i" style={k(1)}>
          Does the linen shirt run small?
        </p>
        <p className="xs-a xv-i" style={k(2)}>
          It runs true to size. Between sizes? Our size guide suggests the larger one.
          <span className="xs-cite">
            <BookOpenText className="size-3.5" aria-hidden />
            Size guide
          </span>
        </p>
      </div>
    </Scene>
  );
}

/** A page's scene. The comment machine and the switch run the landing's own script (ExplainerMotion `scenes`). */
export function AutomationSceneView({ scene }: { scene: AutomationScene }) {
  switch (scene) {
    case "comments":
      // The landing's comment-to-DM machine: one round of comments while on screen, with its pause control.
      return (
        <div className="xs xs-machine ap-wide" data-motion-scope="">
          <CommentMachine />
        </div>
      );
    case "modes":
      // The landing's Off / Suggest / Auto switch, wired by the landing's script.
      return (
        <div className="xs xs-modes ap-wide" data-modes="">
          <ModeSwitch />
        </div>
      );
    case "story":
      return <StoryScene />;
    case "keywords":
      return <KeywordScene />;
    case "starters":
      return <StartersScene />;
    case "widget":
      return <WidgetScene />;
  }
}

/** The hub's scene: the hero inbox every automation hands off to; its one sort plays as it arrives. */
export function HubInbox() {
  return (
    <div className="xs xs-inbox" data-xv="">
      <HeroInbox toggle={false} />
    </div>
  );
}

/** Whether a scene needs the landing's script (the machine and the switch). */
export function sceneNeedsLandingScript(scene: AutomationScene): boolean {
  return scene === "comments" || scene === "modes";
}
