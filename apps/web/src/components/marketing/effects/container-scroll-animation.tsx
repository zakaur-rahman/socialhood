"use client";

import { m, useScroll, useTransform } from "framer-motion";
import { useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Container Scroll Animation, from Aceternity UI's free "container-scroll-animation"
 * (ui.aceternity.com/components/container-scroll-animation), adapted for Social Hood (C-068):
 * - the card tilts back (rotateX 20° → 0) and grows (94% → 100%) as it scrolls up to the middle
 *   of the screen; there is no tall scroll container, so nothing is scroll-jacked;
 * - it never grows past its column (the original scaled to 105%, which overflowed on phones);
 * - with reduced motion it is flat and still (a CSS override, so the server and client markup
 *   stay the same);
 * - the frame uses the surface and line tokens; no title slot (the hero renders its own text).
 */
export function ContainerScroll({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "center center"] });
  const rotateX = useTransform(scrollYProgress, [0, 1], [20, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [0.94, 1]);

  return (
    <div ref={ref} className={cn("relative [perspective:1000px]", className)}>
      <m.div
        style={{ rotateX, scale }}
        className="mx-auto w-full origin-top rounded-2xl border border-line-strong bg-panel p-1.5 shadow-2xl shadow-brand/15 will-change-transform motion-reduce:transform-none! sm:p-2"
      >
        <div className="overflow-hidden rounded-xl border border-line bg-canvas">{children}</div>
      </m.div>
    </div>
  );
}
