import type { ReactNode } from "react";

/**
 * Body blocks of the automation pages (C-163) that the guides don't have. The guides' own blocks
 * (`GuideH2`, `StepCards`, `Pair`, `Checklist`, components/marketing/guides/blocks) and `Callout` do
 * the rest. Styles: site.css, the C-163 auto block.
 */

/** One line of an example: their message, our reply, a button they tap, or what happens in between. */
export type ExampleLine = { who: "them" | "you" | "tap" | "note"; text: ReactNode };

/**
 * A labelled example conversation (no fake proof): a short title, the made-up setting, then the
 * lines as a small thread. Always captioned as example data.
 */
export function ExampleThread({ title, setting, lines }: { title: string; setting: string; lines: ExampleLine[] }) {
  return (
    <figure className="ap-ex" aria-label={`Example: ${title}`}>
      <figcaption className="ap-ex-h">
        <b>{title}</b>
        <span className="ap-ex-tag">Example data</span>
      </figcaption>
      <p className="ap-ex-set">{setting}</p>
      <ol className="ap-ex-thread">
        {lines.map((line, index) => (
          <li key={index} className={`ap-ex-${line.who}`}>
            {line.who === "them" ? <span className="sr-only">Customer: </span> : null}
            {line.who === "you" ? <span className="sr-only">Your automation: </span> : null}
            {line.who === "tap" ? <span className="sr-only">They tap: </span> : null}
            {line.text}
          </li>
        ))}
      </ol>
    </figure>
  );
}
