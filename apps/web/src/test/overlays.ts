import { expect } from "vitest";

/** An element's classes, in order. */
export const classes = (element: Element) => (element.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);

/** The modal family's motion (DESIGN_SYSTEM §7.2): Dialog, AlertDialog and Sheet, and their scrims. */
export const MODAL_MOTION_CLASSES = [
  "data-open:animate-in",
  "data-open:fade-in-0",
  "data-open:duration-slow",
  "data-open:ease-enter",
  "data-closed:animate-out",
  "data-closed:fade-out-0",
  "data-closed:duration-fast",
  "data-closed:ease-exit",
];

/**
 * Every animation is cancelled under reduced motion (DESIGN_SYSTEM §7.4) on its own state variant.
 * `data-open:` and `data-closed:` are custom variants that Tailwind emits after `motion-reduce:`, so
 * a bare `motion-reduce:animate-none` loses to them (the QA baseline's Ask panel).
 */
export function expectReducedMotionCancels(element: Element) {
  const list = classes(element);
  const animated = list.filter((c) => /:animate-(in|out)$/.test(c));
  expect(animated.length).toBeGreaterThan(0);
  for (const c of animated) {
    expect(list).toContain(`${c.replace(/:animate-(in|out)$/, "")}:motion-reduce:animate-none`);
  }
}

/** The modal scrim: black 60%, fading with its panel, no blur (DESIGN_SYSTEM §6). */
export function expectModalScrim(overlay: Element) {
  expect(overlay).toHaveClass("bg-scrim", ...MODAL_MOTION_CLASSES);
  const list = classes(overlay);
  expect(list.filter((c) => c.includes("blur") || c.startsWith("bg-black") || c === "duration-100")).toEqual([]);
  expectReducedMotionCancels(overlay);
}
