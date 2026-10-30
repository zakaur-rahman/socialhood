"use client";

import { useEffect } from "react";

import { startTocSpy } from "./toc-spy";

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
 * The client island behind `TocNav` (C-159), on the guides and the legal pages: renders nothing, and
 * starts the section spy (`startTocSpy`) after load at an idle moment, so it never competes with the
 * page's first paint. Without it the contents still work as plain links.
 */
export function TocSpy() {
  useEffect(() => {
    let stop: (() => void) | undefined;
    let cancelled = false;
    void loaded().then(() => {
      if (!cancelled) stop = startTocSpy(document);
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, []);
  return null;
}
