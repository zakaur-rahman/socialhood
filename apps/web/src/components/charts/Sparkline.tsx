import { cn } from "@/lib/utils";

import { seriesStyle } from "./palette";
import { runsOf } from "./scale";

/**
 * A line with no axes, for a tile: one series, zero-based, the latest point marked. Decorative
 * unless given a `label`, which becomes its accessible name (say the values in it, the way
 * `LineChart`'s table does); the number it sits beside is the real figure. A gap breaks the line.
 */
export function Sparkline({
  values,
  color = 0,
  fixedTop,
  label,
  className,
}: {
  values: (number | null | undefined)[];
  color?: number;
  fixedTop?: number;
  label?: string;
  className?: string;
}) {
  const known = values.filter((v): v is number => v !== null && v !== undefined);
  if (known.length === 0) return null;
  const top = fixedTop ?? Math.max(1, ...known);
  const runs = runsOf(values, top, 4);
  const last = [...runs].reverse()[0]?.at(-1);
  const style = seriesStyle(color);
  return (
    <span className={cn("relative block h-8 w-full", className)} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} data-testid="sparkline">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible">
        {runs.map((run, index) =>
          run.length > 1 ? (
            <polyline key={index} points={run.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" className={style.line} />
          ) : null,
        )}
      </svg>
      {last ? <span className={cn("absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-panel", style.bg)} style={{ left: `${last[0]}%`, top: `${last[1]}%` }} /> : null}
    </span>
  );
}
