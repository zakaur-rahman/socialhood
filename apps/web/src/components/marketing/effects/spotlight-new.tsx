import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/**
 * Spotlight, from Aceternity UI's free "spotlight-new" (ui.aceternity.com/components/spotlight-new),
 * adapted for Social Hood (C-068):
 * - brand-tinted light from the tokens instead of fixed blue HSL values;
 * - no fade-in: the first paint is the finished hero (the original faded in over 1.5 s);
 * - the slow drift is a CSS animation (effects.css), so it ships no JavaScript and runs on the
 *   compositor, only without prefers-reduced-motion;
 * - decorative: aria-hidden, no pointer events, clipped by its section.
 */

// Three soft cones per side, as in the original, from the brand colours at low strength.
const CORE = "radial-gradient(68.54% 68.72% at 55.02% 31.46%, color-mix(in srgb, var(--color-brand-fg) 13%, transparent) 0, color-mix(in srgb, var(--color-brand) 4%, transparent) 50%, transparent 80%)";
const SIDE = "radial-gradient(50% 50% at 50% 50%, color-mix(in srgb, var(--color-brand-fg) 10%, transparent) 0, color-mix(in srgb, var(--color-brand) 3%, transparent) 80%, transparent 100%)";
const FAR = "radial-gradient(50% 50% at 50% 50%, color-mix(in srgb, var(--color-brand-fg) 7%, transparent) 0, color-mix(in srgb, var(--color-brand-deep) 4%, transparent) 80%, transparent 100%)";

type Side = "left" | "right";

function Beams({ side, translateY, width, height, smallWidth }: { side: Side; translateY: number; width: number; height: number; smallWidth: number }) {
  const sign = side === "left" ? -1 : 1;
  const cone = (background: string, style: CSSProperties): CSSProperties => ({ background, height, ...style });
  return (
    <div
      className={cn(
        "absolute top-0 h-dvh w-screen",
        side === "left"
          ? "left-0 motion-safe:animate-[sh-drift-right_7s_ease-in-out_infinite_alternate]"
          : "right-0 motion-safe:animate-[sh-drift-left_7s_ease-in-out_infinite_alternate]",
      )}
    >
      <div
        className={cn("absolute top-0", side === "left" ? "left-0" : "right-0")}
        style={cone(CORE, { width, transform: `translateY(${translateY}px) rotate(${sign * 45}deg)` })}
      />
      <div
        className={cn("absolute top-0", side === "left" ? "left-0 origin-top-left" : "right-0 origin-top-right")}
        style={cone(SIDE, { width: smallWidth, transform: `rotate(${sign * 45}deg) translate(${-sign * 5}%, -50%)` })}
      />
      <div
        className={cn("absolute top-0", side === "left" ? "left-0 origin-top-left" : "right-0 origin-top-right")}
        style={cone(FAR, { width: smallWidth, transform: `rotate(${sign * 45}deg) translate(${sign * 180}%, -70%)` })}
      />
    </div>
  );
}

export function Spotlight({
  translateY = -350,
  width = 560,
  height = 1380,
  smallWidth = 240,
  className,
}: {
  translateY?: number;
  width?: number;
  height?: number;
  smallWidth?: number;
  className?: string;
}) {
  return (
    <div
      aria-hidden
      data-effect="spotlight"
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden",
        className,
      )}
    >
      <Beams side="left" translateY={translateY} width={width} height={height} smallWidth={smallWidth} />
      <Beams side="right" translateY={translateY} width={width} height={height} smallWidth={smallWidth} />
    </div>
  );
}
