/**
 * The hero's routing diagram (C-141): where messages come from, the hub, and what comes out, as
 * numbers on one coordinate system. The server draws the tracks (SVG) and places the nodes (HTML,
 * in percent of the same box) from these numbers, and the client pulses ride the same paths, so
 * every endpoint lines up at any width. Two layouts: `wide` (sources left, outcomes right) from
 * `lg`, and `stack` (sources on top, outcomes below) for phones and tablets.
 */

export type Point = readonly [number, number];

export type SourceId = "ig-dm" | "ig-comment" | "whatsapp" | "web" | "facebook";
export type OutcomeId = "reply" | "needs-you" | "payment" | "sheets" | "report";
/** What colours a pulse: brand coming in, success for an answer out, warning for a hand-off. */
export type Tone = "brand" | "success" | "warning";

export type RoutedNode<Id extends string> = { id: Id; at: Point; path: Point[] };

export type RoutingLayout = {
  name: "wide" | "stack";
  width: number;
  height: number;
  hub: { at: Point; size: number };
  /** A node tile's side, in the layout's units. */
  tile: number;
  sources: RoutedNode<SourceId>[];
  outcomes: RoutedNode<OutcomeId>[];
  /** The two things the AI answers from, each joined to the hub by a dotted track. */
  knowledge: { id: "knowledge" | "catalogue"; at: Point; path: Point[] }[];
  /** Corner radius of the tracks. */
  radius: number;
  /** A travelling pulse's length. */
  dash: number;
  /** How far a riding chip sits from the pulse's head (positive: above it), for each direction. */
  chipOffset: { in: number; out: number };
  /** Where a riding chip's centre may go along x, so it never leaves the box. */
  chipClamp: readonly [number, number];
};

// ---------------------------------------------------------------- geometry

type Segment =
  | { kind: "line"; from: Point; to: Point; length: number }
  | { kind: "arc"; centre: Point; startDir: Point; endDir: Point; radius: number; length: number; to: Point; sweep: 0 | 1 };

function sub(a: Point, b: Point): Point {
  return [a[0] - b[0], a[1] - b[1]];
}
function len(v: Point): number {
  return Math.hypot(v[0], v[1]);
}
function unit(v: Point): Point {
  const l = len(v) || 1;
  return [v[0] / l, v[1] / l];
}
function along(p: Point, dir: Point, distance: number): Point {
  return [p[0] + dir[0] * distance, p[1] + dir[1] * distance];
}

/** An orthogonal polyline with its corners rounded, as straight and quarter-arc segments. */
function segments(points: Point[], radius: number): Segment[] {
  const out: Segment[] = [];
  let cursor = points[0];
  for (let i = 1; i < points.length; i++) {
    const corner = points[i];
    const dirIn = unit(sub(corner, points[i - 1]));
    const next = points[i + 1];
    if (!next) {
      out.push({ kind: "line", from: cursor, to: corner, length: len(sub(corner, cursor)) });
      break;
    }
    const dirOut = unit(sub(next, corner));
    const r = Math.min(radius, len(sub(corner, points[i - 1])) / 2, len(sub(next, corner)) / 2);
    const start = along(corner, dirIn, -r);
    const end = along(corner, dirOut, r);
    out.push({ kind: "line", from: cursor, to: start, length: len(sub(start, cursor)) });
    const cross = dirIn[0] * dirOut[1] - dirIn[1] * dirOut[0];
    out.push({
      kind: "arc",
      centre: along(start, dirOut, r),
      startDir: [-dirOut[0], -dirOut[1]],
      endDir: dirIn,
      radius: r,
      length: (Math.PI * r) / 2,
      to: end,
      sweep: cross > 0 ? 1 : 0,
    });
    cursor = end;
  }
  return out;
}

const round = (value: number) => Math.round(value * 100) / 100;

/** The SVG `d` of a track: straight runs joined by quarter circles. */
export function trackD(points: Point[], radius: number): string {
  const parts = [`M${round(points[0][0])} ${round(points[0][1])}`];
  for (const segment of segments(points, radius)) {
    const [x, y] = segment.to;
    parts.push(segment.kind === "line" ? `L${round(x)} ${round(y)}` : `A${round(segment.radius)} ${round(segment.radius)} 0 0 ${segment.sweep} ${round(x)} ${round(y)}`);
  }
  return parts.join(" ");
}

/** A track's length, and the point at a distance along it (clamped to its ends). */
export function trackSampler(points: Point[], radius: number) {
  const parts = segments(points, radius);
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  function at(distance: number): Point {
    let left = Math.max(0, Math.min(total, distance));
    for (const part of parts) {
      if (left <= part.length) {
        const f = part.length === 0 ? 0 : left / part.length;
        if (part.kind === "line") return [part.from[0] + (part.to[0] - part.from[0]) * f, part.from[1] + (part.to[1] - part.from[1]) * f];
        const angle = (f * Math.PI) / 2;
        const { centre, startDir, endDir, radius: r } = part;
        return [centre[0] + r * (startDir[0] * Math.cos(angle) + endDir[0] * Math.sin(angle)), centre[1] + r * (startDir[1] * Math.cos(angle) + endDir[1] * Math.sin(angle))];
      }
      left -= part.length;
    }
    return points[points.length - 1];
  }
  return { total, at };
}

/** A position in the layout as CSS percentages of its box. */
export function percent(layout: RoutingLayout, [x, y]: Point): { left: string; top: string } {
  return { left: `${round((x / layout.width) * 100)}%`, top: `${round((y / layout.height) * 100)}%` };
}

// ---------------------------------------------------------------- the two layouts

/** From a source at `at` into the hub: across, down or up to its port, then into the hub. */
function intoHub(at: Point, hub: Point, port: number, turn: number | null): Point[] {
  if (turn === null) return [at, [hub[0], at[1]]];
  return [at, [turn, at[1]], [turn, hub[1] + port], [hub[0], hub[1] + port]];
}
/** The mirror: out of the hub's right side to an outcome. */
function outOfHub(at: Point, hub: Point, port: number, turn: number | null): Point[] {
  if (turn === null) return [[hub[0], at[1]], at];
  return [[hub[0], hub[1] + port], [turn, hub[1] + port], [turn, at[1]], at];
}

const WIDE_HUB: Point = [500, 290];
const WIDE_ROWS = [70, 180, 290, 400, 510];
// Left x for each row, staggered; the outcomes mirror them. A track's turn moves nearer the hub
// the further its row is from the middle, so no two tracks cross.
const WIDE_X = [170, 80, 210, 100, 180];
const WIDE_PORTS = [-28, -14, 0, 14, 28];
const WIDE_TURNS = [320, 290, null, 290, 320];
const SOURCE_ORDER: SourceId[] = ["ig-dm", "ig-comment", "whatsapp", "web", "facebook"];
const OUTCOME_ORDER: OutcomeId[] = ["reply", "needs-you", "payment", "sheets", "report"];

export const WIDE: RoutingLayout = {
  name: "wide",
  width: 1000,
  height: 600,
  hub: { at: WIDE_HUB, size: 120 },
  tile: 60,
  sources: SOURCE_ORDER.map((id, i) => {
    const at: Point = [WIDE_X[i], WIDE_ROWS[i]];
    return { id, at, path: intoHub(at, WIDE_HUB, WIDE_PORTS[i], WIDE_TURNS[i]) };
  }),
  outcomes: OUTCOME_ORDER.map((id, i) => {
    const at: Point = [1000 - WIDE_X[i], WIDE_ROWS[i]];
    const turn = WIDE_TURNS[i];
    return { id, at, path: outOfHub(at, WIDE_HUB, WIDE_PORTS[i], turn === null ? null : 1000 - turn) };
  }),
  knowledge: [
    { id: "knowledge", at: [410, 112], path: [[410, 112], [410, 190], [470, 190], [470, 290]] },
    { id: "catalogue", at: [590, 112], path: [[590, 112], [590, 190], [530, 190], [530, 290]] },
  ],
  radius: 12,
  dash: 70,
  chipOffset: { in: 40, out: 52 },
  chipClamp: [130, 870],
};

const STACK_HUB: Point = [170, 270];
const STACK_X = [34, 102, 170, 238, 306];
const STACK_PORTS = [-24, -12, 0, 12, 24];
// Turns for the sources (top row) and the outcomes (bottom row): the outer tracks turn nearest the hub.
const STACK_IN_TURNS = [196, 170, null, 170, 196];
const STACK_OUT_TURNS = [352, 378, null, 378, 352];

function stackIn(at: Point, port: number, turn: number | null): Point[] {
  if (turn === null) return [at, [at[0], STACK_HUB[1]]];
  return [at, [at[0], turn], [STACK_HUB[0] + port, turn], [STACK_HUB[0] + port, STACK_HUB[1]]];
}
function stackOut(at: Point, port: number, turn: number | null): Point[] {
  if (turn === null) return [[at[0], STACK_HUB[1]], at];
  return [[STACK_HUB[0] + port, STACK_HUB[1]], [STACK_HUB[0] + port, turn], [at[0], turn], at];
}

export const STACK: RoutingLayout = {
  name: "stack",
  width: 340,
  height: 530,
  hub: { at: STACK_HUB, size: 84 },
  tile: 44,
  sources: SOURCE_ORDER.map((id, i) => {
    const at: Point = [STACK_X[i], 40];
    return { id, at, path: stackIn(at, STACK_PORTS[i], STACK_IN_TURNS[i]) };
  }),
  outcomes: OUTCOME_ORDER.map((id, i) => {
    const at: Point = [STACK_X[i], 448];
    return { id, at, path: stackOut(at, STACK_PORTS[i], STACK_OUT_TURNS[i]) };
  }),
  knowledge: [
    { id: "knowledge", at: [50, 270], path: [[50, 270], [170, 270]] },
    { id: "catalogue", at: [290, 270], path: [[290, 270], [170, 270]] },
  ],
  radius: 10,
  dash: 44,
  chipOffset: { in: -34, out: 40 },
  chipClamp: [118, 222],
};

export const LAYOUTS = { wide: WIDE, stack: STACK } as const;

// ---------------------------------------------------------------- the examples the pulses carry

export type RoutingExample = {
  from: SourceId;
  to: OutcomeId;
  tone: Tone;
  /** The customer's message, and its language for screen readers (hidden here, but true). */
  ask: { text: string; lang: "en" | "hi-Latn" };
  answer: { text: string; lang: "en" | "hi-Latn" };
};

/** A made-up shop's messages, in English and Hinglish (C-141). */
export const ROUTING_EXAMPLES: RoutingExample[] = [
  {
    from: "ig-dm",
    to: "reply",
    tone: "success",
    ask: { text: "Is the blue kurta in M?", lang: "en" },
    answer: { text: "Yes, ₹1,499. Shall I send the link?", lang: "en" },
  },
  {
    from: "whatsapp",
    to: "payment",
    tone: "success",
    ask: { text: "Haan, M wala bhej do", lang: "hi-Latn" },
    answer: { text: "UPI link sent: ₹1,499", lang: "en" },
  },
  {
    from: "ig-comment",
    to: "needs-you",
    tone: "warning",
    ask: { text: "Mera order damaged aaya", lang: "hi-Latn" },
    answer: { text: "Needs you: passed to your team", lang: "en" },
  },
  {
    from: "web",
    to: "sheets",
    tone: "success",
    ask: { text: "Do you take bulk orders?", lang: "en" },
    answer: { text: "Lead added to Google Sheets", lang: "en" },
  },
];
