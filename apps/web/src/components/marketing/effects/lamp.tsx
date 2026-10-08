"use client";

import { m, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";

/**
 * Lamp, from Aceternity UI's free "lamp" (ui.aceternity.com/components/lamp), adapted for Social
 * Hood (C-068) as a decorative glow above the final call to action:
 * - only the light: the section renders its own heading and buttons on top, server-side;
 * - brand and canvas tokens instead of cyan and slate; no backdrop blur;
 * - it opens once, when it scrolls into view; with reduced motion it is already open;
 * - aria-hidden, no pointer events, a fixed height (no layout shift).
 */
export function LampGlow({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  const transition = reduce ? { duration: 0 } : { delay: 0.2, duration: 0.8, ease: "easeInOut" as const };
  const open = { opacity: 1, width: "30rem" };
  const viewport = { once: true, margin: "0px 0px -20% 0px" };
  return (
    <div aria-hidden data-effect="lamp" className={cn("pointer-events-none absolute inset-x-0 top-0 isolate h-80 overflow-hidden", className)}>
      <div className="relative flex h-full w-full scale-y-125 items-center justify-center max-sm:scale-x-60">
        <m.div
          initial={{ opacity: 0.5, width: "15rem" }}
          whileInView={open}
          viewport={viewport}
          transition={transition}
          style={{ backgroundImage: "conic-gradient(from 70deg at center top, color-mix(in srgb, var(--color-brand) 65%, transparent), transparent, transparent)" }}
          className="absolute right-1/2 h-56 w-[30rem]"
        >
          <div className="absolute bottom-0 left-0 z-20 h-40 w-full bg-canvas [mask-image:linear-gradient(to_top,white,transparent)]" />
          <div className="absolute bottom-0 left-0 z-20 h-full w-40 bg-canvas [mask-image:linear-gradient(to_right,white,transparent)]" />
        </m.div>
        <m.div
          initial={{ opacity: 0.5, width: "15rem" }}
          whileInView={open}
          viewport={viewport}
          transition={transition}
          style={{ backgroundImage: "conic-gradient(from 290deg at center top, transparent, transparent, color-mix(in srgb, var(--color-brand) 65%, transparent))" }}
          className="absolute left-1/2 h-56 w-[30rem]"
        >
          <div className="absolute right-0 bottom-0 z-20 h-full w-40 bg-canvas [mask-image:linear-gradient(to_left,white,transparent)]" />
          <div className="absolute right-0 bottom-0 z-20 h-40 w-full bg-canvas [mask-image:linear-gradient(to_top,white,transparent)]" />
        </m.div>
        <div className="absolute top-1/2 h-48 w-full translate-y-12 scale-x-150 bg-canvas blur-2xl" />
        <div className="absolute z-50 h-36 w-[28rem] max-w-full -translate-y-1/2 rounded-full bg-brand opacity-25 blur-3xl" />
        <m.div
          initial={{ width: "8rem" }}
          whileInView={{ width: "16rem" }}
          viewport={viewport}
          transition={transition}
          className="absolute z-30 h-36 w-64 -translate-y-24 rounded-full bg-brand opacity-45 blur-2xl"
        />
        <m.div
          initial={{ width: "15rem" }}
          whileInView={{ width: "30rem" }}
          viewport={viewport}
          transition={transition}
          className="absolute z-50 h-0.5 w-[30rem] max-w-full -translate-y-28 bg-brand-fg"
        />
        <div className="absolute z-40 h-44 w-full -translate-y-50 bg-canvas" />
      </div>
    </div>
  );
}
