import type { Route } from "next";
import Link from "next/link";

import { cn } from "@/lib/utils";

const count = new Intl.NumberFormat("en-US");

export type MeterLevel = "normal" | "warning" | "full";

/** UX-SCR-07 meters: the fill turns warning at 80% and danger at 100%. */
export function meterLevel(used: number, limit: number | null | undefined): MeterLevel {
  if (!limit) return "normal";
  const share = used / limit;
  if (share >= 1) return "full";
  if (share >= 0.8) return "warning";
  return "normal";
}

const FILL: Record<MeterLevel, string> = {
  normal: "bg-brand-gradient-decor",
  warning: "bg-warning",
  full: "bg-danger",
};

/**
 * UX-CMP-02 UsageMeter: "{used} of {limit} {unit}" with a bar. At 100% it says which limit and
 * offers the upgrade link (§4.1: every limit says which limit and what to do).
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
  const level = meterLevel(used, limit);
  const percent = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="space-y-1.5" data-level={level}>
      <div className="flex items-baseline justify-between gap-3 text-xs">
        <span className="text-fg-secondary">{label}</span>
        <span className="tabular-nums text-fg-secondary">
          {limit ? `${count.format(used)} of ${count.format(limit)} ${unit}` : `${count.format(used)} ${unit} · no limit`}
        </span>
      </div>
      {limit ? (
        <div
          role="meter"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={Math.min(used, limit)}
          aria-valuetext={`${count.format(used)} of ${count.format(limit)} ${unit}`}
          className="h-1.5 overflow-hidden rounded-full bg-raised"
        >
          <span className={cn("block h-full rounded-full", FILL[level])} style={{ width: `${percent}%` }} />
        </div>
      ) : null}
      {level === "full" && fullMessage ? (
        <p className="flex flex-wrap items-center gap-2 text-xs text-danger-fg" role="status">
          {fullMessage}
          {upgradeHref ? (
            <Link href={upgradeHref} className="font-medium text-brand-fg underline-offset-4 hover:underline">
              Upgrade
            </Link>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
