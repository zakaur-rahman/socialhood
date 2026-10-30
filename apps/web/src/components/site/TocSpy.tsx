"use client";

import { useEffect } from "react";

import { startTocSpy } from "./toc-spy";

/**
 * The client island behind `TocNav` (C-159): renders nothing, and starts the section spy at an idle
 * moment after load, so it never competes with the page's first paint.
 */
export function TocSpy() {
  useEffect(() => {
    let stop: (() => void) | undefined;
    const start = () => {
      stop = startTocSpy();
    };
    const idle = typeof window.requestIdleCallback === "function";
    const handle = idle ? window.requestIdleCallback(start, { timeout: 2000 }) : window.setTimeout(start, 200);
    return () => {
      if (idle) window.cancelIdleCallback(handle);
      else window.clearTimeout(handle);
      stop?.();
    };
  }, []);
  return null;
}
