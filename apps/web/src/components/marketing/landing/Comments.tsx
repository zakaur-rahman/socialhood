import { Hand, Link2, MessageCircle, MessageSquareReply, Send } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { MotionToggle } from "@/components/site/MotionToggle";

import { CREATOR, COMMENT_STREAM, DEFAULT_KEYWORD, DM_SCRIPT } from "./data";

/** The automation's steps (FR-AUT-21 tap first, FR-AUT-22 the follow nudge), as the site has described them. */
const STEPS = [
  { icon: MessageCircle, title: <>Someone comments <b data-kw-show="">{DEFAULT_KEYWORD}</b></>, body: "On any post or Reel, or only the ones you choose." },
  { icon: MessageSquareReply, title: <>A public reply, if you want one</>, body: "“Sent you a DM!” under their comment." },
  { icon: Hand, title: <>Tap first</>, body: "The DM opens with a button, and the link follows their tap." },
  { icon: Link2, title: <>The link, and a polite follow nudge</>, body: "Never a condition for getting the link." },
];

const avatar = (n: number) => ({ "--bg": `var(--av-${n})` }) as CSSProperties;

/** The comments the still frame shows: the first four of the stream, newest first. */
function seedComments() {
  return COMMENT_STREAM.slice(0, 4)
    .reverse()
    .map((comment) => ({ ...comment, text: comment.text.replace("{K}", DEFAULT_KEYWORD).replace("{k}", DEFAULT_KEYWORD.toLowerCase()) }));
}

/**
 * "Comment LINK, get the link in a DM" (C-155): a creator's Reel, the automation, and the DM it
 * sends. Server-rendered with a few comments and a finished DM; when it comes on screen (and motion
 * is allowed) one round of comments arrives, the ones with the keyword light up and a DM is sent for
 * each, then it holds (C-157: no endless loop, and a pause control while it plays). The keyword
 * field changes the keyword the scene listens for.
 */
export function Comments() {
  return (
    <section className="sec" id="automations" aria-labelledby="automations-title" data-motion-scope="">
      <div className="wrap">
        <div className="split-head">
          <h2 id="automations-title" className="h2">
            Comment LINK, get the link in a DM
          </h2>
          <p className="lede">
            Turn comments into conversations, the way Instagram allows. Replies are queued to stay within Instagram&apos;s
            sending limits, so a busy post is handled safely.{" "}
            <Link href="/guides/comment-to-dm-automations">Read the comment-to-DM guide</Link>
          </p>
        </div>

        <CommentMachine />
      </div>
    </section>
  );
}

/**
 * The scene itself (C-155): the Reel, the automation and the DM, with its caption and pause control.
 * Also shown by /how-it-works (C-160); the motion script needs it inside a `[data-motion-scope]`.
 */
export function CommentMachine() {
  const sample = COMMENT_STREAM.find((comment) => comment.match && comment.name)!;
  return (
    <>
      <div className="machine" data-machine="">
        <div className="post" data-ui="">
          <div className="post-img" aria-hidden>
            <span className="reel">Reel</span>
            <span className="cover">My studio tour</span>
          </div>
          <p className="post-cap">
            <b>{CREATOR.handle}</b> {CREATOR.post}
          </p>
          <ul className="comments" data-comments="" aria-label="Comments on the Reel (example)">
            {seedComments().map((comment) => (
              <li key={comment.user} className={`cmt${comment.match ? " match" : ""}${comment.spam ? " spam" : ""}`}>
                <span className="av" style={avatar(comment.avatar)} aria-hidden>
                  {comment.user.charAt(0).toUpperCase()}
                </span>
                <span className="body">
                  <b>{comment.user}</b>
                  {comment.match ? <span className="kw">{comment.text}</span> : comment.text}
                </span>
                {comment.spam ? <span className="tag t-stop">Hidden</span> : null}
              </li>
            ))}
          </ul>
        </div>

        <div className="rule" data-rule="" data-ui="">
          <h3 className="rule-h">Automation on this Reel</h3>
          <ol className="rsteps">
            {STEPS.map(({ icon: Icon, title, body }, index) => (
              <li key={index} className="rstep">
                <span className="ic" aria-hidden>
                  <Icon className="size-4" />
                </span>
                <span>
                  <b>{title}</b>
                  <br />
                  {body}
                </span>
              </li>
            ))}
          </ol>
          <div className="kwfield">
            <label htmlFor="kw">The keyword is yours</label>
            <input id="kw" data-kw="" type="text" maxLength={10} defaultValue={DEFAULT_KEYWORD} autoComplete="off" spellCheck={false} />
          </div>
          <p className="rule-stat">
            <span>DMs sent from this Reel</span>
            <b className="num" data-sent="">
              28
            </b>
          </p>
        </div>

        <div className="dm" data-ui="">
          <div className="dm-h">
            <span className="av" data-dm-av="" style={avatar(sample.avatar)} aria-hidden>
              {sample.user.charAt(0).toUpperCase()}
            </span>
            <span>
              <b data-dm-name="">{sample.user}</b>
              Direct message
            </span>
          </div>
          <div className="dm-b" data-dm="">
            <p className="pb l">
              {DM_SCRIPT.opener}
              <span className="tapbtn">{DM_SCRIPT.button}</span>
            </p>
            <p className="pb r">{DM_SCRIPT.button}</p>
            <p className="pb l">
              {DM_SCRIPT.link}
              <span className="lnk">{DM_SCRIPT.url}</span>
            </p>
            <p className="dm-note">{DM_SCRIPT.followNote}</p>
            <p className="pb l">{DM_SCRIPT.follow}</p>
          </div>
        </div>
        <span className="token" data-token="" aria-hidden>
          <Send className="size-3" strokeWidth={2.4} />
          DM
        </span>
      </div>

      <div className="machine-foot">
        <p className="cap">Example data</p>
        <MotionToggle label="Pause the example" />
      </div>
    </>
  );
}
