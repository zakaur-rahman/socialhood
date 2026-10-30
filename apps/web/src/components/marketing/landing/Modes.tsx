import type { CSSProperties } from "react";

import { MODE_MESSAGES, MODES, type ModeKey } from "./data";

/** The mode the server renders: Suggest, what Free includes. */
export const DEFAULT_MODE: ModeKey = "suggest";

const ORDER: ModeKey[] = ["off", "suggest", "auto"];

/**
 * Off, Suggest and Auto (C-155): a switch over four example messages, and what each mode does with
 * them (the setup steps moved to their own band before pricing, C-157). Server-rendered on Suggest; the switch works once the page's
 * script has loaded (landing-motion.ts), with the buttons' pressed state and the description
 * announced politely.
 */
export function Modes() {
  return (
    <section className="sec modes-sec" id="modes" aria-labelledby="modes-title" data-modes="">
      <div className="wrap">
        {/* A short lede sits under its heading, not in a far column (C-157 organize). */}
        <h2 id="modes-title" className="h2">
          Off, Suggest or Auto, for each account
        </h2>
        <p className="lede">Try the switch to see what each does with the same four messages.</p>
        <ModeSwitch />
      </div>
    </section>
  );
}

/**
 * The switch, its description and the table (C-155). Also shown by /how-it-works (C-160); the script
 * (landing-motion.ts) wires it inside any `[data-modes]` element.
 */
export function ModeSwitch() {
  const mode = MODES[DEFAULT_MODE];
  return (
    <>
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
      <div className="mtable" data-ui="" role="table" aria-label="What happens to four example messages">
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
    </>
  );
}
