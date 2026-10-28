"use client";

import { LazyMotion, MotionConfig } from "framer-motion";
import type { ReactNode } from "react";

/** Resolves once the page has loaded and the browser is idle (C-152). */
function settled(): Promise<void> {
  return new Promise((resolve) => {
    const idle = () => {
      if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(() => resolve(), { timeout: 3000 });
      else setTimeout(resolve, 1000);
    };
    if (document.readyState === "complete") idle();
    else window.addEventListener("load", idle, { once: true });
  });
}

// Motion's animation features arrive after the page has settled (C-152), so neither their download
// nor the re-render they cause lands in the load; until then the `m` elements are their still frame.
const loadFeatures = () => settled().then(() => import("./motion-features")).then((module) => module.default);

/**
 * The landing page's motion settings (C-068). MotionConfig reducedMotion="user" turns transform
 * and layout animations off for visitors who ask for reduced motion; the effects also check it
 * themselves to stop loops and scroll-linked movement. LazyMotion keeps motion's animation code
 * out of the first load: `m` components render at once and animate when it has arrived.
 */
export function MarketingMotion({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={loadFeatures} strict>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  );
}
