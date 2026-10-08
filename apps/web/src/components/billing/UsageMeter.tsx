import type { Route } from "next";
import Link from "next/link";

import { Meter } from "@/components/ui/meter";

/**
 * UX-CMP-02 UsageMeter: "{used} of {limit} {unit}" with a bar. At 100% it says which limit and
 * offers the upgrade link (§4.1: every limit says which limit and what to do). A thin wrapper over
 * Meter, which owns the thresholds, the bar and `role="meter"`.
 */
export function UsageMeter({
  label,
  used,
  limit,
  unit,
  fullMessage,
  upgradeHref,
}: {
  label: string;
  used: number;
  /** null: unlimited. */
  limit: number | null | undefined;
  unit: string;
  /** Shown at 100%, e.g. "Your plan includes 200,000 characters of knowledge." */
  fullMessage?: string;
  upgradeHref?: Route;
}) {
  return (
    <Meter
      label={label}
      value={used}
      max={limit}
      unit={unit}
      fullMessage={fullMessage}
      action={
        fullMessage && upgradeHref ? (
          <Link href={upgradeHref} className="font-medium text-brand-fg underline-offset-4 hover:underline">
            Upgrade
          </Link>
        ) : undefined
      }
    />
  );
}
