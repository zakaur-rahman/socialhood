"use client";

import { useEffect } from "react";

/** Resolves once the page has loaded (and, where the browser can say, it has a moment to spare). */
function loaded(): Promise<void> {
  return new Promise((resolve) => {
    const next = () => {
      if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(() => resolve(), { timeout: 800 });
      else setTimeout(resolve, 200);
    };
    if (document.readyState === "complete") next();
    else window.addEventListener("load", next, { once: true });
  });
}

/**
 * The landing page's only client island (C-155): renders nothing, and once the page has loaded it
 * fetches the scenes' script (landing-motion.ts) and starts it over the server-rendered markup. So
 * no animation code is in the first load, and the page is complete without it (C-152's "motion
 * after load", now without framer-motion).
 */
export function LandingMotion() {
  useEffect(() => {
    let stop: (() => void) | undefined;
    let cancelled = false;
    void loaded()
      .then(() => import("./landing-motion"))
      .then(({ startLandingMotion }) => {
        if (!cancelled) stop = startLandingMotion(document);
      });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, []);
  return null;
}
