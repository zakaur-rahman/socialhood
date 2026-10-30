import { ArrowRight, BookOpenText, CircleAlert, FileText, Globe, Link2, MessageCircleQuestionMark, PauseCircle, ShoppingBag, Type } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { INTEGRATIONS } from "@/components/marketing/landing/Channels";
import { CommentMachine } from "@/components/marketing/landing/Comments";
import { HERO_NOTES, KNOWLEDGE, SHOP, SOURCES } from "@/components/marketing/landing/data";
import { HeroInbox } from "@/components/marketing/landing/Hero";
import { Ico } from "@/components/marketing/landing/Ico";
import { ModeSwitch } from "@/components/marketing/landing/Modes";
import { SITE_NAME } from "@/lib/marketing/site";

import type { CellVisual, StageId } from "./content";

/**
 * The small product scenes of /how-it-works and /features (C-160). Each is a `data-ui` fragment in the
 * landing's scene language (sheets, rows, chips, channel marks), server-rendered in its finished
 * state. Inside a `[data-xv]` scene, the `.xv-i` parts arrive once, in order (`--k`), when the scene
 * first comes into view (explainer-motion.ts arms only scenes that start off screen; no loop, and
 * nothing moves with reduced motion or without script). Every name, number and message is example data
 * from the landing's own (data.ts), and the scenes say so.
 */

const k = (n: number) => ({ "--k": n }) as CSSProperties;
const mark = (colour: string) => ({ "--c": colour }) as CSSProperties;
const tone = { live: "var(--ok)", waiting: "var(--wait-mark)", yours: "var(--iris)" } as const;

function Scene({ className, label, children, caption = true }: { className: string; label: string; children: ReactNode; caption?: boolean }) {
  return (
    <figure className={`xs ${className}`} data-xv="">
      <div className="xs-box" data-ui="" role="img" aria-label={label}>
        {children}
      </div>
      {caption ? <figcaption className="cap">Example data</figcaption> : null}
    </figure>
  );
}

// ---------------------------------------------------------------- the stages

const CONNECT = [
  { name: "Instagram", how: "Instagram's own login" },
  { name: "WhatsApp", how: "Meta's Embedded Signup" },
  { name: "Website chat", how: "One line of code on your site" },
  { name: "Facebook Pages", how: "Messenger and Page comments" },
];

function ConnectScene() {
  return (
    <figure className="xs xs-connect" data-xv="">
      <ul className="xs-conn" data-ui="">
        {CONNECT.map((item, index) => {
          const channel = INTEGRATIONS.find((row) => row.name === item.name)!;
          return (
            <li key={item.name} className="xs-conn-row xv-i" style={k(index)}>
              <Ico className="ico-mark" style={mark(channel.mark!)}>
                <PlatformGlyph platform={channel.platform!} />
              </Ico>
              <span className="xs-conn-t">
                <b>{item.name}</b>
                <span>{item.how}</span>
              </span>
              <span className="st" style={{ "--sc": tone[channel.tone] } as CSSProperties}>
                {channel.status}
              </span>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

const SOURCES_SHOWN = [
  { icon: Type, title: KNOWLEDGE[1].title, kind: "Questions and answers" },
  { icon: FileText, title: KNOWLEDGE[0].title, kind: "File" },
  { icon: Link2, title: "Returns policy", kind: "Link" },
  { icon: Globe, title: "indigolane.example", kind: "Website, 12 pages" },
  { icon: ShoppingBag, title: "Product catalogue", kind: "Pro" },
];

function KnowledgeScene() {
  return (
    <Scene className="xs-know" label={`Example: ${SHOP}'s knowledge, five sources, and a test question answered from the delivery FAQ.`}>
      <div className="xs-card">
        <p className="xs-h">
          <b>{SHOP}&apos;s knowledge</b>
          <span>{SOURCES_SHOWN.length} sources</span>
        </p>
        <ul className="xs-src">
          {SOURCES_SHOWN.map((source, index) => (
            <li key={source.title} className="xv-i" style={k(index)}>
              <source.icon className="size-4" aria-hidden />
              <b>{source.title}</b>
              <span>{source.kind}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="xs-card xs-test xv-i" style={k(5)}>
        <p className="xs-h">
          <b>Test a question</b>
        </p>
        <p className="xs-q">How long does delivery take?</p>
        <p className="xs-a">
          Orders ship within 2 working days, and delivery takes 3 to 5 days.
          <span className="xs-cite">
            <BookOpenText className="size-3.5" aria-hidden />
            {KNOWLEDGE[1].title}
          </span>
        </p>
      </div>
    </Scene>
  );
}

function ReadsScene() {
  return (
    <Scene className="xs-reads" label="Example: a customer's Instagram DM tagged as a product question, neutral, with a lead score of 72 out of 100.">
      <div className="xs-card">
        <div className="xs-msg">
          <span className="av" style={{ "--bg": "var(--av-2)" } as CSSProperties}>
            M
          </span>
          <span>
            <b>Maya R.</b>
            <span className="app" style={mark(SOURCES.dm.colour)}>
              <i />
              {SOURCES.dm.label}
            </span>
          </span>
        </div>
        <p className="xs-bub">Is the linen shirt in M? Do you deliver to Toronto?</p>
        <dl className="xs-tags">
          <div className="xv-i" style={k(0)}>
            <dt>Intent</dt>
            <dd>
              <span className="tag t-plain">Product question</span>
            </dd>
          </div>
          <div className="xv-i" style={k(1)}>
            <dt>Sentiment</dt>
            <dd>
              <span className="tag t-plain">Neutral</span>
            </dd>
          </div>
          <div className="xv-i" style={k(2)}>
            <dt>Lead score</dt>
            <dd>
              <b className="num xs-score">72</b>
              <span className="xs-of">of 100</span>
            </dd>
          </div>
        </dl>
      </div>
    </Scene>
  );
}

function HandoffScene() {
  return (
    <Scene className="xs-hand" label="Example: a question the knowledge doesn't cover goes to Needs you, is recorded as a knowledge gap, and the AI pauses after you reply.">
      <div className="night xs-night">
        <p className="bub in xv-i" style={k(0)}>
          Do you take bulk orders?
        </p>
        <p className="handoff xv-i" style={k(1)}>
          <CircleAlert className="size-4.5" aria-hidden />
          <span>
            <b>The answer isn&apos;t in your knowledge, so the AI doesn&apos;t guess.</b> The conversation goes to Needs you.
          </span>
        </p>
        <p className="gap xv-i" style={k(2)}>
          <span>Knowledge gap: bulk orders</span>
          <b>Add an answer</b>
        </p>
        <p className="xs-paused xv-i" style={k(3)}>
          <PauseCircle className="size-4" aria-hidden />
          You replied, so the AI pauses here for 2 hours.
        </p>
      </div>
    </Scene>
  );
}

const REPORT = [
  ["Messages received", "214"],
  ["Reply rate", "96%"],
  ["First response", "4 min"],
  ["Handled by the AI", "61%"],
  ["Still needs you", "3"],
] as const;

function ReportCard() {
  return (
    <div className="xs-card xs-report">
      <p className="xs-h">
        <b>Your week</b>
        <span>Monday, 9:00 AM</span>
      </p>
      <dl className="xs-stats">
        {REPORT.map(([label, value], index) => (
          <div key={label} className="xv-i" style={k(index)}>
            <dt>{label}</dt>
            <dd className="num">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="xs-top xv-i" style={k(REPORT.length)}>
        <span>Top question</span>
        Do you deliver to Toronto?
      </p>
    </div>
  );
}

function AskCard({ compact = false }: { compact?: boolean }) {
  return (
    <div className="xs-card xs-ask">
      <p className="xs-h">
        <b>
          <MessageCircleQuestionMark className="size-4" aria-hidden />
          Ask {SITE_NAME}
        </b>
      </p>
      <p className="xs-q xv-i" style={k(0)}>
        Which post brought the most DMs last week?
      </p>
      {compact ? null : (
        <p className="xs-a xv-i" style={k(1)}>
          Your Reel &ldquo;My studio tour&rdquo;: 28 DMs from comments, Monday to Sunday.
          <span className="xs-cite">From your automations</span>
        </p>
      )}
    </div>
  );
}

function ResultsScene() {
  return (
    <Scene className="xs-results" label={`Example: the Monday weekly report, and a question to Ask ${SITE_NAME} answered with the figures it used.`}>
      <ReportCard />
      <AskCard />
    </Scene>
  );
}

/** A stage's scene: the landing's own scenes where they fit (imported, not copied), cards elsewhere. */
export function StageVisual({ id }: { id: StageId }) {
  switch (id) {
    case "connect":
      return <ConnectScene />;
    case "knowledge":
      return <KnowledgeScene />;
    case "inbox":
      // The hero's inbox; its one sort plays when it comes into view (explainer-motion.ts).
      return (
        <div className="xs xs-inbox" data-xv="">
          <HeroInbox toggle={false} />
        </div>
      );
    case "reads":
      return <ReadsScene />;
    case "replies":
      // The landing's Off / Suggest / Auto switch, wired by the landing's script.
      return (
        <div className="xs xs-modes" data-modes="">
          <ModeSwitch />
        </div>
      );
    case "handoff":
      return <HandoffScene />;
    case "automations":
      // The landing's comment-to-DM machine: one round of comments while on screen, with its pause control.
      return (
        <div className="xs xs-machine" data-motion-scope="">
          <CommentMachine />
        </div>
      );
    case "results":
      return <ResultsScene />;
  }
}

// ---------------------------------------------------------------- the bento cells

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SLOTS: Record<number, string> = { 0: "Post", 2: "Reel", 3: "Story", 5: "Carousel" };

/** A bento cell's mini scene (/features): smaller, quieter versions of the stage scenes. */
export function CellVisual({ visual }: { visual: CellVisual }) {
  switch (visual) {
    case "inbox":
      return (
        <Scene className="xs-mini xs-rows" label="Example: four conversations from Instagram, WhatsApp and website chat in one inbox." caption={false}>
          <ul>
            {HERO_NOTES.filter((note) => note.source !== "comment")
              .slice(0, 4)
              .map((note, index) => (
                <li key={note.name} className="xv-i" style={k(index)}>
                  <span className="app" style={mark(SOURCES[note.source].colour)}>
                    <i />
                  </span>
                  <b>{note.name}</b>
                  <span className="xs-rt">{note.text}</span>
                  <span className={`tag t-${note.tone}`}>{note.tag}</span>
                </li>
              ))}
          </ul>
        </Scene>
      );
    case "replies":
      return (
        <Scene className="xs-mini xs-draft" label="Example: an AI draft answering from the price list, and a question it hands to you." caption={false}>
          <p className="xs-q xv-i" style={k(0)}>
            Is the linen shirt in M?
          </p>
          <div className="xs-dr xv-i" style={k(1)}>
            <span className="xs-dr-h">AI draft</span>
            <p>Yes, the linen shirt comes in S to XL, for $39.</p>
            <span className="xs-cite">{KNOWLEDGE[0].title}</span>
          </div>
          <p className="xs-need xv-i" style={k(2)}>
            <span className="tag t-need">Needs you</span>
            Do you take bulk orders?
          </p>
        </Scene>
      );
    case "comments":
      return (
        <Scene className="xs-mini xs-c2d" label="Example: a comment with the keyword LINK, and the DM that sends the link." caption={false}>
          <p className="xs-cmt xv-i" style={k(0)}>
            <b>sam.films</b> <span className="kw">LINK</span>
          </p>
          <ArrowRight className="xs-arrow xv-i size-4" style={k(1)} aria-hidden />
          <p className="xs-dm xv-i" style={k(2)}>
            Here&apos;s the full gear list.
            <span className="lnk">mia.example/gear</span>
          </p>
        </Scene>
      );
    case "publishing":
      return (
        <Scene className="xs-mini xs-week" label="Example: a week on the calendar with a post, a Reel, a Story and a carousel scheduled." caption={false}>
          <ol>
            {DAYS.map((day, index) => (
              <li key={day}>
                <span>{day}</span>
                {SLOTS[index] ? (
                  <b className="xv-i" style={k(index)}>
                    {SLOTS[index]}
                  </b>
                ) : null}
              </li>
            ))}
          </ol>
        </Scene>
      );
    case "insight":
      return (
        <Scene className="xs-mini xs-chips" label="Example: a post's comments sorted into questions, buying signals and hidden spam." caption={false}>
          <span className="tag t-plain xv-i" style={k(0)}>
            12 questions
          </span>
          <span className="tag t-ok xv-i" style={k(1)}>
            5 buying signals
          </span>
          <span className="tag t-stop xv-i" style={k(2)}>
            2 spam, hidden
          </span>
        </Scene>
      );
    case "analytics":
      return (
        <Scene className="xs-mini xs-duo" label="Example: a reply rate of 96% and a first response of 4 minutes." caption={false}>
          <p className="xv-i" style={k(0)}>
            <b className="num">96%</b>
            <span>Reply rate</span>
          </p>
          <p className="xv-i" style={k(1)}>
            <b className="num">4 min</b>
            <span>First response</span>
          </p>
        </Scene>
      );
    case "ask":
      return (
        <Scene className="xs-mini xs-askm" label={`Example: a question to Ask ${SITE_NAME}.`} caption={false}>
          <p className="xs-q xv-i" style={k(0)}>
            Which post brought the most DMs last week?
          </p>
        </Scene>
      );
  }
}
