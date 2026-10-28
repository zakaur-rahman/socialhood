import type { CSSProperties } from "react";

import { MODE_MESSAGES, MODES, type ModeKey } from "./data";

/** The three setup steps, as the site has always described them. */
export const SETUP_STEPS = [
  {
    title: "Connect your accounts",
    body: "Connect your Instagram professional account with Instagram's own login, and your WhatsApp Business number through Meta's official setup. Amplychat never asks for your password.",
  },
  {
    title: "Add your knowledge",
    body: "Prices, products, delivery, returns, timings and FAQs, as text, a link or a file. Test a question to see how the AI would answer before customers ask.",
  },
  {
    title: "Let the AI draft or reply",
    body: "Start with Suggest and send the drafts you like. On Pro, switch an account to Auto: the AI replies when it's confident and hands everything else to you.",
  },
];

/** The mode the server renders: Suggest, what Free includes. */
export const DEFAULT_MODE: ModeKey = "suggest";

const ORDER: ModeKey[] = ["off", "suggest", "auto"];

/**
 * Off, Suggest and Auto (C-155): a switch over four example messages, and what each mode does with
 * them, then the three setup steps. Server-rendered on Suggest; the switch works once the page's
 * script has loaded (landing-motion.ts), with the buttons' pressed state and the description
 * announced politely.
 */
export function Modes() {
  const mode = MODES[DEFAULT_MODE];
  return (
    <section className="sec modes-sec" id="modes" aria-labelledby="modes-title" data-modes="">
      <div className="wrap">
        <div className="split-head">
          <div>
            <p className="kicker">Set up in three steps</p>
            <h2 id="modes-title" className="h2">
              Let the AI draft or reply
            </h2>
          </div>
          <p className="lede">
            Choose Off, Suggest or Auto for each account. Try the switch to see what each does with the same four messages.
          </p>
        </div>
        <div className="switch" role="group" aria-label="AI reply mode">
          {ORDER.map((key) => (
            <button key={key} type="button" data-mode={key} aria-pressed={key === DEFAULT_MODE}>
              {MODES[key].label}
              {key === "auto" ? <span className="pro">Pro</span> : null}
            </button>
          ))}
        </div>
        <p className="mode-desc" data-mode-desc="" aria-live="polite">
          {mode.description}
        </p>
        <div className="mtable" role="table" aria-label="What happens to four example messages">
          <div className="mrow head" role="row">
            <span role="columnheader">Message</span>
            <span role="columnheader">Tagged as</span>
            <span role="columnheader">What happens</span>
          </div>
          {MODE_MESSAGES.map((message, index) => {
            const [tone, tag, note] = mode.outcomes[index];
            return (
              <div key={message.text} className="mrow" role="row">
                <span className="msg" role="cell">
                  <span className="av" style={{ "--bg": `var(--av-${message.avatar})` } as CSSProperties} aria-hidden>
                    {message.from.split("· ")[1].charAt(0)}
                  </span>
                  <span>
                    {message.text}
                    <small>{message.from}</small>
                  </span>
                </span>
                <span className="lab" role="cell">
                  {message.label}
                </span>
                <span className="out" role="cell" data-out={index}>
                  <span className={`tag t-${tone}`}>{tag}</span>
                  <small>{note}</small>
                </span>
              </div>
            );
          })}
        </div>

        <ol className="steps">
          {SETUP_STEPS.map((step, index) => (
            <li key={step.title}>
              <span className="n">Step {index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
