"use client";

import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";

import type { LAYOUTS } from "../routing";

type LayoutName = keyof typeof LAYOUTS;

/**
 * The routing diagram's pulses (C-141). It shows `still` (the still frame, rendered on the server:
 * the first example's two tracks lit faintly and both chips in place) until three things hold:
 * the page has settled (idle after the load event), the diagram has been on screen, and the visitor
 * allows motion. Only then does it download the moving layer (RoutingPulsesLive, with motion's
 * code) and swap it in, so none of it is in the page's load or its first frames (C-152). With
 * reduced motion, or without JavaScript, the still frame stays.
 */
export function RoutingPulses({ layout, still }: { layout: LayoutName; still: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [Live, setLive] = useState<ComponentType<{ layout: LayoutName }> | null>(null);

  useEffect(() => {
    const box = ref.current;
    if (!box || !("IntersectionObserver" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let cancelled = false;
    let settled = false;
    let seen = false;
    let idle: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const start = () => {
      if (!settled || !seen || cancelled) return;
      observer.disconnect();
      void import("./RoutingPulsesLive").then((module) => {
        if (!cancelled) setLive(() => module.default);
      });
    };
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        seen = true;
        start();
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    observer.observe(box);

    const onIdle = () => {
      settled = true;
      start();
    };
    const afterLoad = () => {
      if (typeof window.requestIdleCallback === "function") idle = window.requestIdleCallback(onIdle, { timeout: 3000 });
      else timer = setTimeout(onIdle, 1000);
    };
    if (document.readyState === "complete") afterLoad();
    else window.addEventListener("load", afterLoad, { once: true });

    return () => {
      cancelled = true;
      observer.disconnect();
      window.removeEventListener("load", afterLoad);
      if (idle !== undefined) window.cancelIdleCallback(idle);
      if (timer !== undefined) clearTimeout(timer);
    };
  }, []);

  return (
    <div ref={ref} data-routing-pulses={Live ? "live" : "still"} className="pointer-events-none absolute inset-0 overflow-hidden">
      {Live ? <Live layout={layout} /> : still}
    </div>
  );
}
