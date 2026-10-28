import { cx } from "@/lib/cx";

import { percent, ROUTING_EXAMPLES, trackD, trackSampler, type Point, type RoutingLayout, type Tone } from "../routing";

/**
 * The routing diagram's pulses (C-141): what the still frame and the moving layer share, the
 * tracks' geometry and the message chip, and the still frame itself. No client code (C-152): the
 * still frame renders on the server and RoutingPulsesLive downloads once the page has settled.
 */

/** How far along its track the still frame places the first message. */
const STILL_AT = { wide: 0.54, stack: 0.3 } as const;

export const STROKE: Record<Tone, string> = { brand: "stroke-brand", success: "stroke-success", warning: "stroke-warning" };
const DOT: Record<Tone, string> = { brand: "bg-brand", success: "bg-success", warning: "bg-warning" };

export type Track = { d: string; total: number; at: (distance: number) => Point };

export function track(points: Point[], layout: RoutingLayout): Track {
  const sampler = trackSampler(points, layout.radius);
  return { d: trackD(points, layout.radius), ...sampler };
}

/** Where a chip's centre sits for a pulse head at `point`, in percent of the diagram. */
export function chipPoint(layout: RoutingLayout, point: Point, offset: number): Point {
  const [min, max] = layout.chipClamp;
  return [Math.min(max, Math.max(min, point[0])), point[1] - offset];
}

/**
 * A message on a chip. `moving` chips fade in and out as they ride, so for a moment their words sit
 * at a fraction of their contrast; they draw the words from CSS (a pseudo-element) rather than a
 * text node. The diagram is decorative (aria-hidden, its summary is in the text) and the still
 * frame keeps real text at full contrast (C-152).
 */
export function Chip({ text, lang, tone, moving = false, className }: { text: string; lang: string; tone: Tone | "ask"; moving?: boolean; className?: string }) {
  return (
    <span
      lang={lang}
      className={cx(
        "flex items-center gap-1.5 rounded-full border border-line-strong bg-overlay px-2.5 py-1 text-xs whitespace-nowrap text-fg shadow-floating",
        className,
      )}
    >
      <span className={cx("size-1.5 shrink-0 rounded-full", tone === "ask" ? "bg-brand" : DOT[tone])} />
      {moving ? <span data-chip-text={text} className="after:content-[attr(data-chip-text)]" /> : text}
    </span>
  );
}

/** The first example's two tracks lit faintly and both chips in place: what shows until the pulses move. */
export function StillFrame({ layout }: { layout: RoutingLayout }) {
  const example = ROUTING_EXAMPLES[0];
  const source = layout.sources.find((node) => node.id === example.from)!;
  const outcome = layout.outcomes.find((node) => node.id === example.to)!;
  const into = track(source.path, layout);
  const out = track(outcome.path, layout);
  const ask = chipPoint(layout, into.at(into.total * STILL_AT[layout.name]), layout.chipOffset.in);
  const answer = chipPoint(layout, out.at(out.total), layout.chipOffset.out);
  return (
    <>
      <svg viewBox={`0 0 ${layout.width} ${layout.height}`} preserveAspectRatio="none" className="absolute inset-0 size-full" fill="none">
        <path d={into.d} className="stroke-brand opacity-60" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        <path d={out.d} className={cx(STROKE[example.tone], "opacity-60")} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="absolute z-10 -translate-x-1/2 -translate-y-1/2" style={percent(layout, ask)}>
        <Chip text={example.ask.text} lang={example.ask.lang} tone="ask" />
      </div>
      <div className="absolute z-10 -translate-x-1/2 -translate-y-1/2" style={percent(layout, answer)}>
        <Chip text={example.answer.text} lang={example.answer.lang} tone={example.tone} />
      </div>
    </>
  );
}
