"use client";

import { m, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";

import { cn } from "@/lib/utils";

import { EASE_STANDARD } from "./motion";

/**
 * A rail that draws itself down a list once it scrolls into view, in the spirit of Aceternity's
 * Tracing Beam (C-068), as a decorative line beside server-rendered steps. Drawn and still with
 * reduced motion.
 */
export function TraceLine({ className, duration = 1.6 }: { className?: string; duration?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -20% 0px" });
  const reduce = useReducedMotion();
  return (
    <div ref={ref} aria-hidden className={cn("pointer-events-none absolute w-0.5 overflow-hidden rounded-full bg-line", className)}>
      <m.div
        className="bg-brand-gradient-decor absolute inset-0 origin-top motion-reduce:transform-none!"
        initial={{ scaleY: 0 }}
        animate={{ scaleY: inView || reduce ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : { duration, ease: EASE_STANDARD }}
      />
    </div>
  );
}
