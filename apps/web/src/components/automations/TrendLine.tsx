import { cn } from "@/lib/utils";

const WIDTH = 60;
const HEIGHT = 20;
const STROKE = 2;

/**
 * UX-SCR-02: the 60 px trend of daily runs over 7 days (oldest first). Decorative: the row
 * states the count in text, so the line is hidden from assistive technology.
 */
export function TrendLine({ values, className }: { values: number[]; className?: string }) {
  if (values.length < 2) return <span aria-hidden className={cn("inline-block h-5 w-[60px]", className)} />;
  const max = Math.max(...values, 1);
  const step = (WIDTH - STROKE) / (values.length - 1);
  const points = values
    .map((value, index) => {
      const x = STROKE / 2 + index * step;
      const y = HEIGHT - STROKE / 2 - (value / max) * (HEIGHT - STROKE);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      aria-hidden
      data-testid="trend-line"
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className={cn("shrink-0 overflow-visible text-brand", className)}
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={STROKE}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
