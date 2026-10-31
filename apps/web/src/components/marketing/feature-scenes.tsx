import { CalendarClock, Check, EyeOff, MessageSquareReply, Send } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { StageVisual } from "@/components/marketing/explainers/visuals";
import type { FeatureScene } from "@/lib/marketing/gtm-pages";

/**
 * The product scenes of the feature pages (C-163), in the scene language of /how-it-works (`.xs`,
 * `data-ui` fragments, the `.xv-i` parts arriving once in order when the scene comes into view; see
 * explainer-motion.ts). Server-rendered in their finished state; nothing moves without script or with
 * reduced motion. Every name, number and message is made up and captioned "Example data". The limits
 * the scenes show (2,200 characters, 30 hashtags) are the composer's real checklist
 * (models/publishing.py CAPTION_MAX_CHARS, MAX_HASHTAGS).
 */

const k = (n: number) => ({ "--k": n }) as CSSProperties;

function Scene({ className, label, children }: { className: string; label: string; children: ReactNode }) {
  return (
    <figure className={`xs ${className}`} data-xv="">
      <div className="xs-box" data-ui="" role="img" aria-label={label}>
        {children}
      </div>
      <figcaption className="cap">Example data</figcaption>
    </figure>
  );
}

// schemas/posts.py PostTopic: a label, its comment count and sentiment.
const TOPICS = [
  { label: "Sizes", count: 41, mood: "Mostly positive", tone: "t-ok" },
  { label: "Price", count: 18, mood: "Neutral", tone: "t-plain" },
  { label: "Delivery", count: 9, mood: "Neutral", tone: "t-plain" },
  { label: "Colours", count: 7, mood: "Mostly positive", tone: "t-ok" },
] as const;

/** A post's summary and topics, the filter chips, and one comment with its actions (schemas/posts.py). */
function CommentsScene() {
  return (
    <Scene
      className="fs-cmts"
      label="Example: a post's comment summary with four topics, filter chips for needs reply, questions, buying signals and hidden spam, and a question with reply, DM and hide actions."
    >
      <div className="xs-card">
        <p className="xs-h">
          <b>Reel: the new linen collection</b>
          <span>Summary</span>
        </p>
        <p className="fs-sum xv-i" style={k(0)}>
          Most people like the new colours and ask which sizes are in stock. Several ask the price of the shirt, and a few ask about delivery times.
        </p>
        <ul className="fs-topics">
          {TOPICS.map((topic, index) => (
            <li key={topic.label} className="xv-i" style={k(index + 1)}>
              <b>{topic.label}</b>
              <span className="num">{topic.count} comments</span>
              <span className={`tag ${topic.tone}`}>{topic.mood}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="xs-card">
        <p className="fs-chips xv-i" style={k(5)}>
          <span className="tag t-need">Needs reply 12</span>
          <span className="tag t-plain">Questions 23</span>
          <span className="tag t-ok">Buying 8</span>
          <span className="tag t-stop">Spam 3, hidden</span>
        </p>
        <div className="fs-cmt xv-i" style={k(6)}>
          <p>
            <b>maya.r</b> Is the linen shirt in M?
          </p>
          <span className="tag t-plain">Product question</span>
          <span className="fs-acts">
            <span>
              <MessageSquareReply className="size-3.5" aria-hidden />
              Reply
            </span>
            <span>
              <Send className="size-3.5" aria-hidden />
              DM
            </span>
            <span>
              <EyeOff className="size-3.5" aria-hidden />
              Hide
            </span>
          </span>
        </div>
      </div>
    </Scene>
  );
}

// services/scheduled_posts/rules.py: the checklist's items.
const CHECKS = ["Carousel, 4 files", "Caption 182 of 2,200 characters", "8 of 30 hashtags", "Every file in a supported size"] as const;

/** The composer's checklist before scheduling (services/scheduled_posts/rules.py checklist). */
function ComposerScene() {
  return (
    <Scene className="fs-comp" label="Example: a carousel in the composer passing its checklist, ready to add to the queue at the next free posting time.">
      <div className="xs-card">
        <p className="xs-h">
          <b>New post</b>
          <span>2 accounts</span>
        </p>
        <ul className="fs-checks">
          {CHECKS.map((check, index) => (
            <li key={check} className="xv-i" style={k(index)}>
              <Check className="size-4" aria-hidden />
              {check}
            </li>
          ))}
        </ul>
        <p className="fs-next xv-i" style={k(CHECKS.length)}>
          <CalendarClock className="size-4" aria-hidden />
          <span>
            Next free posting time <b>Friday, 6:00 PM</b>
          </span>
        </p>
      </div>
    </Scene>
  );
}

const WEEK = [
  { day: "Mon" },
  { day: "Tue", post: "Post", time: "6:00 PM" },
  { day: "Wed" },
  { day: "Thu", post: "Reel", time: "7:30 PM" },
  { day: "Fri", free: "6:00 PM" },
  { day: "Sat", post: "Story", time: "10:00 AM" },
  { day: "Sun" },
] as const;

/** A week on the calendar: scheduled posts and a free posting time (services/scheduled_posts/calendar.py). */
function CalendarScene() {
  return (
    <Scene className="fs-cal" label="Example: a week on the calendar with a photo post on Tuesday, a Reel on Thursday, a Story on Saturday and a free posting time on Friday.">
      <div className="xs-card">
        <p className="xs-h">
          <b>This week</b>
          <span>Week view</span>
        </p>
        <ol className="fs-week">
          {WEEK.map((slot, index) => (
            <li key={slot.day}>
              <span>{slot.day}</span>
              {"post" in slot ? (
                <b className="xv-i" style={k(index)}>
                  {slot.post}
                  <small>{slot.time}</small>
                </b>
              ) : null}
              {"free" in slot ? (
                <i className="xv-i" style={k(index)}>
                  Free
                  <small>{slot.free}</small>
                </i>
              ) : null}
            </li>
          ))}
        </ol>
      </div>
    </Scene>
  );
}

/** A feature page's scene by name. The inbox's is /how-it-works' hand-off scene, imported, not copied. */
export function FeatureSceneView({ scene }: { scene: FeatureScene }) {
  switch (scene) {
    case "inbox":
      return <StageVisual id="handoff" />;
    case "comments":
      return <CommentsScene />;
    case "composer":
      return <ComposerScene />;
    case "calendar":
      return <CalendarScene />;
  }
}
