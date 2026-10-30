"use client";

import { useEffect } from "react";

/** Resolves once the page has loaded and the browser has a moment to spare (as LandingMotion). */
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
 * The explainer pages' only client island (C-160): renders nothing; after load, at an idle moment, it
 * fetches explainer-motion.ts and starts it (the step tracker, the scenes playing once, and on
 * /how-it-works the landing's scene script). The pages are complete without it.
 */
export function ExplainerMotion({ scenes = false }: { scenes?: boolean }) {
  useEffect(() => {
    let stop: (() => void) | undefined;
    let cancelled = false;
    void loaded()
      .then(() => import("./explainer-motion"))
      .then(({ startExplainerMotion }) => startExplainerMotion(document, { scenes }))
      .then((cleanup) => {
        if (cancelled) cleanup();
        else stop = cleanup;
      });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [scenes]);
  return null;
}
