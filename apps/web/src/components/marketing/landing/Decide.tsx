import { CircleAlert } from "lucide-react";
import type { CSSProperties } from "react";

import { MotionToggle } from "@/components/site/MotionToggle";
import { SECTION_IDS } from "@/lib/marketing/site";

import { KNOWLEDGE, SHOP } from "./data";

/** The four things the AI does with a message, from the feature cards. */
export const DECIDE_STEPS = [
  { title: "Reads the message", body: "Tagged with intent, sentiment and a lead score" },
  { title: "Searches your knowledge", body: "Only what's in your knowledge base" },
  { title: "Drafts or sends the reply", body: "Off, Suggest or Auto, for each account" },
  { title: "Hands over when unsure", body: "And records the gap, so you know what to add" },
];

/** The draft, as text with the cited spans marked: [text, cite]. */
const DRAFT: [string, ("a" | "b" | "c")?][] = [
  ["Yes, the linen shirt comes "],
  ["in S to XL, for $39.", "a"],
  [" Orders "],
  ["ship within 2 working days", "b"],
  [" and "],
  ["arrive in 3 to 5 days.", "c"],
  [" Shall I send you the order link?"],
];

/**
 * "How it works" on a night band (C-155; C-157 makes it the page's one peak): the shop's knowledge
 * on the left, a conversation on the right. The AI's draft points to the lines it used, and a
 * question the knowledge doesn't cover goes to Needs you as a gap. The heading sits inside the
 * pinned frame, and the frame opens on the customer's question, already tagged, never empty.
 * Server-rendered with every step shown; on wide screens about one screen of scroll plays it (a scan
 * over the knowledge, wires to the cited words, the draft writing itself, the hand-off and the gap),
 * on phones it plays once when on screen (with a pause control), and with reduced motion it stays
 * as rendered.
 */
export function Decide() {
  return (
    <section className="night decide" id={SECTION_IDS.howItWorks} aria-labelledby="decide-title" data-decide="" data-motion-scope="">
      <div className="decide-scrub" data-decide-scrub="">
        <div className="decide-sticky" data-decide-sticky="">
          <div className="wrap">
            <div className="decide-head">
              <h2 id="decide-title" className="h2">
                AI replies from your own knowledge
              </h2>
              <p className="lede">
                The AI is instructed to answer only from your knowledge base and your conversation. When the answer isn&apos;t
                there, it doesn&apos;t guess: it hands the conversation to you and records the question as a knowledge gap.
              </p>
            </div>
            <div className="decide-grid" data-dgrid="">
              <div className="kb" data-kb="" data-ui="">
                <div className="kb-h">
                  <span>{SHOP}&apos;s knowledge</span>
                  <span>{KNOWLEDGE.length} sources</span>
                </div>
                {KNOWLEDGE.map((doc) => (
                    <div key={doc.title} className="doc">
                      <p className="doc-h">{doc.title}</p>
                      <ul>
                        {doc.lines.map((line) => (
                          <li key={line.text} className={line.cite ? "line hit" : "line"} data-m={line.cite}>
                            <span>{line.text}</span>
                            {line.right ? <span className="r num">{line.right}</span> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                ))}
                <div className="scan" data-scan="" aria-hidden />
              </div>
              <svg className="wires" data-wires="" aria-hidden />
              <div className="thread" data-ui="">
                <div className="thread-h">
                  <span className="av" style={{ "--bg": "var(--av-1)" } as CSSProperties}>
                    M
                  </span>
                  <span>
                    <b>Maya R.</b>
                    <span className="app" style={{ "--c": "var(--ig)" } as CSSProperties}>
                      <i />
                      Instagram DM
                    </span>
                  </span>
                  <MotionToggle className="decide-toggle" label="Pause the example" />
                </div>
                <div className="thread-b">
                  <p className="bub in" data-q1="">
                    Is the linen shirt in M? Do you deliver to Toronto? How long does it take?
                  </p>
                  <p className="read fx" data-read="">
                    Tagged: product question
                  </p>
                  <div className="ddraft fx" data-draft="">
                    <div className="ddraft-h">
                      <span>AI draft</span>
                      <span className="state" data-dstate="">
                        Ready to send
                      </span>
                    </div>
                    <p className="ddraft-t" data-dtext="">
                      {DRAFT.map(([text, cite], index) =>
                        cite ? (
                          <span key={index} className="src" data-m={cite}>
                            {text}
                          </span>
                        ) : (
                          <span key={index}>{text}</span>
                        ),
                      )}
                    </p>
                    <ul className="cites fx" data-cites="">
                      <li className="cite">
                        <i />
                        Price list, line 1
                      </li>
                      <li className="cite">
                        <i />
                        Delivery FAQ, lines 1 and 2
                      </li>
                    </ul>
                  </div>
                  <p className="bub in fx" data-q2="">
                    Do you take bulk orders?
                  </p>
                  <p className="handoff fx" data-hand="">
                    <CircleAlert className="size-4.5" aria-hidden />
                    <span>
                      <b>The answer isn&apos;t in your knowledge, so the AI doesn&apos;t guess.</b> The conversation goes to
                      Needs you.
                    </span>
                  </p>
                  <p className="gap fx" data-gap="">
                    <span>Knowledge gap: bulk orders</span>
                    <b>Add an answer</b>
                  </p>
                </div>
              </div>
            </div>
            <ol className="dsteps" data-dsteps="">
              {DECIDE_STEPS.map((step) => (
                <li key={step.title}>
                  <b>{step.title}</b>
                  {step.body}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
