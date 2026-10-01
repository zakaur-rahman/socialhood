"use client";

import { m, useAnimationFrame, useInView, useMotionTemplate, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Moving Border, from Aceternity UI's free "moving-border" (ui.aceternity.com/components/moving-border),
 * adapted for Social Hood (C-068) as a frame around a card instead of a button:
 * - a soft brand glow travels along the card's edge, one lap every `duration` ms;
 * - the frame loop runs only while the card is on screen, and never with reduced motion: then
 *   the edge is a still brand line;
 * - the glow and edge use the brand tokens; decorative and aria-hidden.
 */
export function MovingBorderFrame({
  children,
  className,
  duration = 6000,
}: {
  children: ReactNode;
  className?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);
  const reduce = useReducedMotion();
  return (
    <div ref={ref} data-frame="moving-border" className={cn("relative overflow-hidden rounded-2xl bg-brand-line p-px", className)}>
      {inView && !reduce ? (
        <div aria-hidden data-effect="moving-border" className="absolute inset-0">
          <MovingBorder duration={duration} rx="16" ry="16">
            <div className="size-28 bg-[radial-gradient(var(--color-brand-fg)_25%,transparent_65%)] opacity-90" />
          </MovingBorder>
        </div>
      ) : null}
      <div className="relative h-full rounded-2xl bg-panel">{children}</div>
    </div>
  );
}

export function MovingBorder({ children, duration = 6000, rx, ry }: { children: ReactNode; duration?: number; rx?: string; ry?: string }) {
  const pathRef = useRef<SVGRectElement>(null);
  const progress = useMotionValue(0);

  useAnimationFrame((time) => {
    const length = pathRef.current?.getTotalLength();
    if (length) progress.set((time * (length / duration)) % length);
  });

  const x = useTransform(progress, (value) => pathRef.current?.getPointAtLength(value).x ?? 0);
  const y = useTransform(progress, (value) => pathRef.current?.getPointAtLength(value).y ?? 0);
  const transform = useMotionTemplate`translateX(${x}px) translateY(${y}px) translateX(-50%) translateY(-50%)`;

  return (
    <>
      <svg preserveAspectRatio="none" className="absolute size-full" width="100%" height="100%">
        <rect fill="none" width="100%" height="100%" rx={rx} ry={ry} ref={pathRef} />
      </svg>
      <m.div style={{ position: "absolute", top: 0, left: 0, display: "inline-block", transform }}>{children}</m.div>
    </>
  );
}
