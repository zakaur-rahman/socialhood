import { Sparkline } from "@/components/charts/Sparkline";
import { cn } from "@/lib/utils";

/**
 * UX-SCR-02: the 60 px trend of daily runs over 7 days (oldest first), one series in the first
 * chart colour with the latest day marked. Decorative: the row states the count in text, so the
 * line is hidden from assistive technology.
 */
export function TrendLine({ values, className }: { values: number[]; className?: string }) {
  if (values.length < 2) return <span aria-hidden className={cn("inline-block h-5 w-[60px]", className)} />;
  return <Sparkline values={values} testId="trend-line" className={cn("h-5 w-[60px] shrink-0", className)} />;
}
