"use client";

import { useEffect } from "react";

/** True where site.css animates the questions' height by itself (`interpolate-size` and `::details-content`). */
export function cssAnimatesDetails(): boolean {
  return typeof CSS !== "undefined" && CSS.supports("interpolate-size: allow-keywords") && CSS.supports("selector(::details-content)");
}

/**
 * The FAQ's open and close (C-157 motion), for browsers where CSS can't animate a `<details>` to its
 * natural height: renders nothing, and only there (and with motion allowed) fetches faq-motion.ts,
 * which runs the same 250 ms move with the Web Animations API. Everywhere else the CSS does it all
 * and this costs one feature test. The questions stay native details and summary either way.
 */
export function FaqMotion() {
  useEffect(() => {
    if (cssAnimatesDetails() || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let stop: (() => void) | undefined;
    let cancelled = false;
    void import("./faq-motion").then(({ bindFaqMotion }) => {
      if (!cancelled) stop = bindFaqMotion(document);
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, []);
  return null;
}
