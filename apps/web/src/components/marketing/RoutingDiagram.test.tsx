import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Hero, HERO_TITLE } from "./Hero";
import { ROUTING_OUTCOMES, ROUTING_SOURCES, ROUTING_SUMMARY, RoutingDiagram } from "./RoutingDiagram";
import { LAYOUTS, ROUTING_EXAMPLES, trackD, trackSampler, type Point, type RoutingLayout } from "./routing";

const parse = (html: string) => new DOMParser().parseFromString(html, "text/html");

/** The orthogonal runs of every track, outside the hub (where they meet on purpose). */
function runs(layout: RoutingLayout): { id: string; from: Point; to: Point }[] {
  const half = layout.hub.size / 2;
  const [hx, hy] = layout.hub.at;
  const inHub = ([x, y]: Point) => Math.abs(x - hx) <= half && Math.abs(y - hy) <= half;
  const clip = (a: Point, b: Point): [Point, Point] | null => {
    // Trim a run to the part outside the hub square (runs are horizontal or vertical).
    const steps = 200;
    const outside: Point[] = [];
    for (let i = 0; i <= steps; i++) {
      const p: Point = [a[0] + ((b[0] - a[0]) * i) / steps, a[1] + ((b[1] - a[1]) * i) / steps];
      if (!inHub(p)) outside.push(p);
    }
    return outside.length > 1 ? [outside[0], outside[outside.length - 1]] : null;
  };
  const all = [...layout.sources, ...layout.outcomes, ...layout.knowledge];
  return all.flatMap((node) =>
    node.path.slice(1).flatMap((to, i) => {
      const clipped = clip(node.path[i], to);
      return clipped ? [{ id: node.id, from: clipped[0], to: clipped[1] }] : [];
    }),
  );
}

function crosses(a: { from: Point; to: Point }, b: { from: Point; to: Point }): boolean {
  const aH = a.from[1] === a.to[1];
  const bH = b.from[1] === b.to[1];
  if (aH === bH) return false;
  const [h, v] = aH ? [a, b] : [b, a];
  const [x1, x2] = [Math.min(h.from[0], h.to[0]), Math.max(h.from[0], h.to[0])];
  const [y1, y2] = [Math.min(v.from[1], v.to[1]), Math.max(v.from[1], v.to[1])];
  const x = v.from[0];
  const y = h.from[1];
  return x > x1 + 0.5 && x < x2 - 0.5 && y > y1 + 0.5 && y < y2 - 0.5;
}

describe("the hero's routing diagram (C-141)", () => {
  it.each(Object.values(LAYOUTS))("$name: every track starts at its node and ends in the hub, and no two cross", (layout) => {
    const [hx, hy] = layout.hub.at;
    const half = layout.hub.size / 2;
    for (const node of layout.sources) {
      expect(node.path[0]).toEqual(node.at);
      const end = node.path[node.path.length - 1];
      expect(Math.abs(end[0] - hx) <= half && Math.abs(end[1] - hy) <= half, node.id).toBe(true);
    }
    for (const node of layout.outcomes) {
      expect(node.path[node.path.length - 1]).toEqual(node.at);
      const start = node.path[0];
      expect(Math.abs(start[0] - hx) <= half && Math.abs(start[1] - hy) <= half, node.id).toBe(true);
    }
    const list = runs(layout);
    for (const a of list) for (const b of list) if (a.id !== b.id) expect(crosses(a, b), `${a.id} × ${b.id}`).toBe(false);
  });

  it("measures tracks with their rounded corners, and samples their ends exactly", () => {
    const points: Point[] = [[0, 0], [100, 0], [100, 50]];
    const { total, at } = trackSampler(points, 10);
    expect(total).toBeCloseTo(150 - 20 + (Math.PI * 10) / 2, 5);
    expect(at(0)).toEqual([0, 0]);
    expect(at(total)[0]).toBeCloseTo(100, 5);
    expect(at(total)[1]).toBeCloseTo(50, 5);
    expect(trackD(points, 10)).toBe("M0 0 L90 0 A10 10 0 0 1 100 10 L100 50");
  });

  it("is in the server's markup: nodes, tracks, hub, labels and a still frame, with one sentence for screen readers", () => {
    const html = renderToStaticMarkup(<RoutingDiagram />);
    const doc = parse(html);
    expect(doc.querySelector("figcaption")?.textContent).toBe(ROUTING_SUMMARY);
    const art = doc.querySelector("[data-routing-diagram]");
    expect(art?.getAttribute("aria-hidden")).toBe("true");

    for (const layout of Object.values(LAYOUTS)) {
      const box = doc.querySelector(`[data-routing-layout="${layout.name}"]`) as HTMLElement;
      expect(box, layout.name).not.toBeNull();
      expect(box.querySelectorAll('[data-side="source"]')).toHaveLength(5);
      expect(box.querySelectorAll('[data-side="outcome"]')).toHaveLength(5);
      expect(box.querySelector('[data-routing-node="hub"] [data-logo-mark]')).not.toBeNull();
      expect(box.querySelectorAll("[data-routing-track]")).toHaveLength(12);
      // Each track's drawing begins where its node is placed.
      for (const node of layout.sources) {
        const d = box.querySelector(`[data-routing-track="${node.id}"]`)?.getAttribute("d") ?? "";
        expect(d.startsWith(`M${node.at[0]} ${node.at[1]}`), node.id).toBe(true);
      }
      // The still frame: the first example's message and answer, before any script runs.
      expect(box.querySelector('[data-routing-pulses="still"]')?.textContent).toContain(ROUTING_EXAMPLES[0].ask.text);
      expect(box.querySelector('[data-routing-pulses="still"]')?.textContent).toContain(ROUTING_EXAMPLES[0].answer.text);
    }

    const wide = doc.querySelector('[data-routing-layout="wide"]')?.textContent ?? "";
    for (const meta of [...Object.values(ROUTING_SOURCES), ...Object.values(ROUTING_OUTCOMES)]) expect(wide).toContain(meta.label);
    expect(doc.querySelector('[data-routing-node="facebook"]')?.textContent).toContain("soon");
    expect(html).not.toMatch(/opacity:\s*0[;"]|visibility:\s*hidden|display:\s*none/);
  });

  it("the hero has one h1 with the headline, and both ways in", () => {
    const doc = parse(renderToStaticMarkup(<Hero />));
    const h1 = doc.querySelectorAll("h1");
    expect(h1).toHaveLength(1);
    expect(h1[0].textContent).toBe(HERO_TITLE);
    expect([...doc.querySelectorAll("a")].map((a) => a.getAttribute("href"))).toEqual(["/sign-up", "#how-it-works"]);
  });

  it("every example starts and ends at a node that exists, and is honest about its language", () => {
    for (const example of ROUTING_EXAMPLES) {
      expect(ROUTING_SOURCES[example.from]).toBeDefined();
      expect(ROUTING_OUTCOMES[example.to]).toBeDefined();
      expect(example.from).not.toBe("facebook");
    }
    expect(ROUTING_EXAMPLES.some((example) => example.ask.lang === "hi-Latn")).toBe(true);
  });
});
