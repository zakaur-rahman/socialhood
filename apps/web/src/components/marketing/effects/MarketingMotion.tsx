"use client";

import { LazyMotion, MotionConfig } from "framer-motion";
import type { ReactNode } from "react";

const loadFeatures = () => import("./motion-features").then((module) => module.default);

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
