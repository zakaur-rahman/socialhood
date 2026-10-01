"use client";

import { m, useReducedMotion } from "framer-motion";

import { DURATION, EASE_STANDARD } from "../effects/motion";

/**
 * An animated beam between two points, in the style of Magic UI's "Animated Beam", built with
 * motion (C-068: Aceternity has no free equivalent). The path draws itself when `active`, then a
 * short brand pulse runs along it (a CSS dash animation, effects.css) while it stays active. With
 * reduced motion the path is drawn and still.
 *
 * Coordinates are in the parent SVG's viewBox; the parent sets the size.
 */
export function Beam({ d, active, delay = 0 }: { d: string; active: boolean; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <g>
      <path d={d} fill="none" stroke="var(--color-line-strong)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      <m.path
        d={d}
        fill="none"
        stroke="var(--color-brand)"
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
        initial={{ pathLength: reduce ? 1 : 0 }}
        animate={{ pathLength: active || reduce ? 1 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.9, ease: EASE_STANDARD, delay }}
      />
      {active && !reduce ? (
        <m.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: DURATION.expressive, delay: delay + 0.9 }}>
          <path
            d={d}
            fill="none"
            stroke="var(--color-brand-fg)"
            strokeWidth={2.5}
            strokeLinecap="round"
            pathLength={100}
            strokeDasharray="12 88"
            vectorEffect="non-scaling-stroke"
            className="animate-[sh-beam_2.4s_linear_infinite]"
          />
        </m.g>
      ) : null}
    </g>
  );
}
