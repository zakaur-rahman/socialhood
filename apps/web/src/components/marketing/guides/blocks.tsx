import { Link2, type LucideIcon } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { sectionId } from "@/lib/marketing/guides/types";

import { Ico } from "../landing/Ico";

/**
 * Building blocks for a guide's body (C-159). Each holds the guide's own words in a structure: a
 * section heading with an anchor, two cards side by side, step cards, a checklist. Styles: site.css,
 * the C-159 guides block (`.gprose`).
 */

/** A section heading: its id comes from its text (the table of contents uses the same), with a link to itself. */
export function GuideH2({ children }: { children: string }) {
  const id = sectionId(children);
  return (
    <h2 id={id}>
      {children}
      <a href={`#${id}`} className="g-anchor" aria-label="Link to this section">
        <Link2 size={16} strokeWidth={1.75} aria-hidden focusable="false" />
      </a>
    </h2>
  );
}

/** Two cards side by side from 640 px (a comparison); stacked below. */
export function Pair({ children }: { children: ReactNode }) {
  return <div className="g-pair">{children}</div>;
}

/** One side of a pair: an icon tile and the guide's own text. `mark` sets the icon's colour (a channel colour). */
export function PairCard({ icon, mark, children }: { icon: LucideIcon; mark?: string; children: ReactNode }) {
  return (
    <div className="g-pcard">
      <Ico icon={icon} className={mark ? "ico-mark" : undefined} style={mark ? ({ "--c": mark } as CSSProperties) : undefined} />
      <div className="g-pcard-b">{children}</div>
    </div>
  );
}

/** Steps or parts as cards: each item is an icon and its text. */
export function StepCards({ items, columns = 2 }: { items: { icon: LucideIcon; body: ReactNode }[]; columns?: 2 | 3 }) {
  return (
    <ol className={`g-steps g-steps-${columns}`}>
      {items.map((item, index) => (
        <li key={index} className="g-step">
          <Ico icon={item.icon} />
          <div>{item.body}</div>
        </li>
      ))}
    </ol>
  );
}

/** An ordered list of things to do, set as a checklist card. */
export function Checklist({ children }: { children: ReactNode }) {
  return <ol className="g-check">{children}</ol>;
}
