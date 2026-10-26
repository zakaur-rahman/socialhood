"use client";

import { m, useAnimationFrame, useInView, useMotionValue, useReducedMotion, useTransform, type MotionValue } from "framer-motion";
import { useMemo, useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { LAYOUTS, percent, ROUTING_EXAMPLES, trackD, trackSampler, type Point, type RoutingExample, type RoutingLayout, type Tone } from "../routing";

/**
 * The routing diagram's moving part (C-141): light pulses that carry a customer's message along a
 * track into the hub, then the answer out to where it goes, each with its words riding on a small
 * chip. One clock drives everything, so the pulses, chips and the nodes' "breath" stay in step.
 *
 * - The first render (the server's, and the one before the diagram is on screen) is a still frame:
 *   the first example's two tracks lit faintly and both chips in place. With reduced motion it
 *   stays that frame; the clock only runs while the diagram is on screen.
 * - Only transforms and opacity move, so nothing shifts the layout.
 */

/** One example's timeline, in seconds from its start. */
const T = {
  cycle: 6.4,
  inStart: 0.5,
  inDur: 1.6,
  thinkStart: 1.9,
  thinkDur: 0.8,
  outStart: 2.6,
  outDur: 1.5,
  restEnd: 5.7,
  fadeEnd: 6.1,
  ring: 0.9,
} as const;
const LOOP = T.cycle * ROUTING_EXAMPLES.length;
/** How far along its track the still frame places the first message. */
const STILL_AT = { wide: 0.54, stack: 0.3 } as const;

const STROKE: Record<Tone, string> = { brand: "stroke-brand", success: "stroke-success", warning: "stroke-warning" };
const RING: Record<Tone, string> = { brand: "border-brand", success: "border-success", warning: "border-warning" };
const DOT: Record<Tone, string> = { brand: "bg-brand", success: "bg-success", warning: "bg-warning" };

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);
/** Eased progress through a window that starts at `start` and lasts `duration`. */
const progress = (local: number, start: number, duration: number) => easeInOut(clamp01((local - start) / duration));
/** This example's own time, or -1 when it isn't playing. */
const localTime = (t: number, index: number) => {
  const local = t - index * T.cycle;
  return local >= 0 && local < T.cycle ? local : -1;
};

type Track = { d: string; total: number; at: (distance: number) => Point };

function track(points: Point[], layout: RoutingLayout): Track {
  const sampler = trackSampler(points, layout.radius);
  return { d: trackD(points, layout.radius), ...sampler };
}

/** Where a chip's centre sits for a pulse head at `point`, in percent of the diagram. */
function chipPoint(layout: RoutingLayout, point: Point, offset: number): Point {
  const [min, max] = layout.chipClamp;
  return [Math.min(max, Math.max(min, point[0])), point[1] - offset];
}

function Chip({ text, lang, tone, className }: { text: string; lang: string; tone: Tone | "ask"; className?: string }) {
  return (
    <span
      lang={lang}
      className={cn(
        "flex items-center gap-1.5 rounded-full border border-line-strong bg-overlay px-2.5 py-1 text-xs whitespace-nowrap text-fg shadow-floating",
        className,
      )}
    >
      <span className={cn("size-1.5 shrink-0 rounded-full", tone === "ask" ? "bg-brand" : DOT[tone])} />
      {text}
    </span>
  );
}

function StillFrame({ layout }: { layout: RoutingLayout }) {
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
        <path d={out.d} className={cn(STROKE[example.tone], "opacity-60")} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
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

/** A dash of light along a track, whose head is at `head` units along it. */
function Pulse({ path, total, dash, head, tone }: { path: string; total: number; dash: number; head: MotionValue<number>; tone: Tone }) {
  const offset = useTransform(head, (h) => dash - h);
  return (
    <>
      <m.path d={path} className={cn(STROKE[tone], "opacity-40 blur-xs")} strokeWidth={5} strokeLinecap="round" strokeDasharray={`${dash} ${total + dash}`} style={{ strokeDashoffset: offset }} />
      <m.path d={path} className={STROKE[tone]} strokeWidth={2} strokeLinecap="round" strokeDasharray={`${dash} ${total + dash}`} style={{ strokeDashoffset: offset }} />
    </>
  );
}

/** A ring that swells out of a node and fades: the node "breathes" when a packet reaches it. */
function Ring({ layout, point, size, tone, clock, at, shape }: { layout: RoutingLayout; point: Point; size: number; tone: Tone; clock: MotionValue<number>; at: (t: number) => number; shape: string }) {
  const phase = useTransform(clock, (t) => {
    const since = at(t);
    return since >= 0 && since < T.ring ? since / T.ring : -1;
  });
  const scale = useTransform(phase, (p) => (p < 0 ? 1 : 1 + 0.4 * easeInOut(p)));
  const opacity = useTransform(phase, (p) => (p < 0 ? 0 : 0.9 * (1 - p)));
  return (
    <div className="absolute aspect-square -translate-x-1/2 -translate-y-1/2" style={{ ...percent(layout, point), width: `${(size / layout.width) * 100}%` }}>
      <m.span className={cn("absolute inset-0 border-2", shape, RING[tone])} style={{ scale, opacity }} />
    </div>
  );
}

/** A chip that rides a pulse: `head` is its distance along `track`, `opacity` when it shows. */
function RidingChip({ layout, along, head, offset, opacity, children }: { layout: RoutingLayout; along: Track; head: MotionValue<number>; offset: number; opacity: MotionValue<number>; children: ReactNode }) {
  const point = useTransform(head, (h) => chipPoint(layout, along.at(h), offset));
  const x = useTransform(point, ([px]) => `${(px / layout.width) * 100}%`);
  const y = useTransform(point, ([, py]) => `${(py / layout.height) * 100}%`);
  return (
    // A full-size layer moved by a percentage of itself (that is, of the diagram), carrying the chip
    // at its top-left corner.
    <m.div className="pointer-events-none absolute inset-0 z-10" style={{ x, y, opacity }}>
      <div className="absolute top-0 left-0 -translate-x-1/2 -translate-y-1/2">{children}</div>
    </m.div>
  );
}

function ExampleLive({ layout, example, index, clock }: { layout: RoutingLayout; example: RoutingExample; index: number; clock: MotionValue<number> }) {
  const source = layout.sources.find((node) => node.id === example.from)!;
  const outcome = layout.outcomes.find((node) => node.id === example.to)!;
  const into = useMemo(() => track(source.path, layout), [source, layout]);
  const out = useMemo(() => track(outcome.path, layout), [outcome, layout]);
  const half = layout.hub.size / 2;
  const fade = layout.dash * 0.6;

  const inHead = useTransform(clock, (t) => {
    const local = localTime(t, index);
    return local < 0 ? 0 : progress(local, T.inStart, T.inDur) * (into.total + layout.dash);
  });
  const outHead = useTransform(clock, (t) => {
    const local = localTime(t, index);
    return local < 0 ? 0 : progress(local, T.outStart, T.outDur) * (out.total + layout.dash);
  });
  const askOpacity = useTransform(clock, (t) => {
    const local = localTime(t, index);
    if (local < 0) return 0;
    const head = Math.min(into.total, progress(local, T.inStart, T.inDur) * (into.total + layout.dash));
    return Math.min(clamp01((local - 0.15) / 0.35), clamp01((into.total - half - head) / fade));
  });
  const answerOpacity = useTransform(clock, (t) => {
    const local = localTime(t, index);
    if (local < 0) return 0;
    const head = Math.min(out.total, progress(local, T.outStart, T.outDur) * (out.total + layout.dash));
    return Math.min(clamp01((head - half) / fade), 1 - clamp01((local - T.restEnd) / (T.fadeEnd - T.restEnd)));
  });
  const askHead = useTransform(inHead, (h) => Math.min(h, into.total));
  const answerHead = useTransform(outHead, (h) => Math.min(h, out.total));

  return (
    <>
      <svg viewBox={`0 0 ${layout.width} ${layout.height}`} preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible" fill="none">
        <Pulse path={into.d} total={into.total} dash={layout.dash} head={inHead} tone="brand" />
        <Pulse path={out.d} total={out.total} dash={layout.dash} head={outHead} tone={example.tone} />
      </svg>
      <Ring layout={layout} point={source.at} size={layout.tile} tone="brand" clock={clock} shape="rounded-2xl" at={(t) => localTime(t, index) - T.inStart + 0.1} />
      <Ring layout={layout} point={layout.hub.at} size={layout.hub.size} tone="brand" clock={clock} shape="rounded-3xl" at={(t) => localTime(t, index) - (T.inStart + T.inDur - 0.15)} />
      <Ring layout={layout} point={outcome.at} size={layout.tile} tone={example.tone} clock={clock} shape="rounded-2xl" at={(t) => localTime(t, index) - (T.outStart + T.outDur - 0.1)} />
      <RidingChip layout={layout} along={into} head={askHead} offset={layout.chipOffset.in} opacity={askOpacity}>
        <Chip text={example.ask.text} lang={example.ask.lang} tone="ask" />
      </RidingChip>
      <RidingChip layout={layout} along={out} head={answerHead} offset={layout.chipOffset.out} opacity={answerOpacity}>
        <Chip text={example.answer.text} lang={example.answer.lang} tone={example.tone} />
      </RidingChip>
    </>
  );
}

/** The dotted ties light up while the hub "thinks": the answer comes from what the business added. */
function KnowledgePulses({ layout, clock }: { layout: RoutingLayout; clock: MotionValue<number> }) {
  const tracks = useMemo(() => layout.knowledge.map((k) => track(k.path, layout)), [layout]);
  const dash = layout.dash * 0.6;
  const heads = [
    useTransform(clock, (t) => {
      const local = t % T.cycle;
      return progress(local, T.thinkStart, T.thinkDur) * (tracks[0].total + dash);
    }),
    useTransform(clock, (t) => {
      const local = t % T.cycle;
      return progress(local, T.thinkStart + 0.08, T.thinkDur) * (tracks[1].total + dash);
    }),
  ];
  return (
    <svg viewBox={`0 0 ${layout.width} ${layout.height}`} preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible" fill="none">
      {tracks.map((k, i) => (
        <Pulse key={layout.knowledge[i].id} path={k.d} total={k.total} dash={dash} head={heads[i]} tone="brand" />
      ))}
    </svg>
  );
}

export function RoutingPulses({ layout: name }: { layout: keyof typeof LAYOUTS }) {
  const layout = LAYOUTS[name];
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { margin: "0px 0px -10% 0px" });
  const seen = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduce = useReducedMotion();
  const clock = useMotionValue(0);
  // Moving from the first time the diagram is on screen, never with reduced motion.
  const live = seen && reduce === false;

  useAnimationFrame((_, delta) => {
    if (!live || !inView) return;
    clock.set((clock.get() + Math.min(delta, 100) / 1000) % LOOP);
  });

  return (
    <div ref={ref} data-routing-pulses={live ? "live" : "still"} className="pointer-events-none absolute inset-0 overflow-hidden">
      {live ? (
        <>
          <KnowledgePulses layout={layout} clock={clock} />
          {ROUTING_EXAMPLES.map((example, index) => (
            <ExampleLive key={example.from} layout={layout} example={example} index={index} clock={clock} />
          ))}
        </>
      ) : (
        <StillFrame layout={layout} />
      )}
    </div>
  );
}
