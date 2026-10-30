/**
 * The explainer pages' motion (C-160), loaded by ExplainerMotion once the page has settled. Plain DOM
 * over the server-rendered markup; every move is a CSS transition or animation on transform and
 * opacity, so no box moves (CLS 0), and nothing here reads layout.
 *
 * - Scenes (`[data-xv]`): a scene that starts off screen is armed (`data-xv="armed"`: its parts wait,
 *   site.css) when the observer first reports it, and plays once (`data-xv="in"`) as it comes into
 *   view. A scene already on screen is never touched, so nothing visible blinks; with no script, or
 *   with reduced motion, every scene simply shows.
 * - Cards (`[data-rise]`): where the browser has no `view()` timeline, the same arm-then-rise for the
 *   cards site.css rises with a scroll timeline elsewhere.
 * - The contents (`[data-toc]`): the step tracker and the side nav mark the current section (toc-spy).
 * - `scenes`: also starts the landing's scene script, for the landing scenes /how-it-works reuses (the
 *   mode switch, the comment-to-DM machine).
 */
import { startTocSpy } from "@/components/site/toc-spy";

type Cleanup = () => void;

/** Arms what starts off screen, then sets `attr` to "in" when it arrives. */
function arrive(elements: HTMLElement[], attr: "xv" | "rv", threshold: number): Cleanup {
  if (!elements.length || typeof IntersectionObserver === "undefined") return () => {};
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const el = entry.target as HTMLElement;
        const state = el.dataset[attr];
        if (entry.isIntersecting) {
          if (state === "armed") el.dataset[attr] = "in";
          observer.unobserve(el);
        } else if (!state) el.dataset[attr] = "armed";
      }
    },
    { threshold },
  );
  elements.forEach((el) => observer.observe(el));
  return () => observer.disconnect();
}

export async function startExplainerMotion(root: Document = document, { scenes = false } = {}): Promise<Cleanup> {
  const cleanups: Cleanup[] = [startTocSpy(root)];
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce) {
    cleanups.push(arrive([...root.querySelectorAll<HTMLElement>("[data-xv]")], "xv", 0.35));
    const timeline = typeof CSS !== "undefined" && CSS.supports?.("animation-timeline: view()");
    if (!timeline) cleanups.push(arrive([...root.querySelectorAll<HTMLElement>("[data-rise]")], "rv", 0));
  }
  if (scenes) {
    const { startLandingMotion } = await import("@/components/marketing/landing/landing-motion");
    cleanups.push(startLandingMotion(root));
  }
  return () => cleanups.forEach((stop) => stop());
}
