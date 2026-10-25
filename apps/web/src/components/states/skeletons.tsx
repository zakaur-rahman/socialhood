import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Shared loading pieces (C-136). Each one has the size of the thing it stands for, so nothing
 * moves when the data arrives: the same card padding and radius (it is the real Card), the same
 * row heights, images at their real aspect ratio. A page builds its skeleton from these.
 *
 * Accessibility: the placeholders are hidden from assistive tech (Skeleton is `aria-hidden`);
 * `SkeletonRegion` is the one `aria-busy` region with the one polite "Loading" label.
 */

/** The region that is loading: `aria-busy`, one polite announcement, placeholders inside are hidden. */
export function SkeletonRegion({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className={className}>
      {children}
    </div>
  );
}

/** A card with a title line and `lines` text lines (a settings card, a list card). */
export function CardSkeleton({ lines = 2, className }: { lines?: number; className?: string }) {
  return (
    <Card className={cn("space-y-3", className)}>
      <Skeleton className="h-4 w-40" />
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-3", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </Card>
  );
}

/** A list row: optional avatar or thumbnail, two text lines, optional trailing badge. */
export function RowSkeleton({
  avatar = "round",
  trailing = false,
  className,
}: {
  avatar?: "round" | "square" | "none";
  trailing?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      {avatar === "none" ? null : (
        <Skeleton className={cn("size-10 shrink-0", avatar === "round" ? "rounded-full" : "rounded-lg")} />
      )}
      <div className="min-w-0 flex-1 space-y-2">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-3 w-2/3" />
      </div>
      {trailing ? <Skeleton className="h-5 w-16 shrink-0 rounded-full" /> : null}
    </div>
  );
}

/** A card holding `count` rows, the height of a real list card's rows (name, meta, badge). */
export function RowCardsSkeleton({ count = 3, lines = 3 }: { count?: number; lines?: 2 | 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }, (_, i) => (
        <Card key={i} className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <Skeleton className="h-5 w-48 max-w-[60%]" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
          <Skeleton className="h-4 w-2/3" />
          {lines === 3 ? <Skeleton className="h-4 w-1/2" /> : null}
        </Card>
      ))}
    </div>
  );
}

/** One metric tile, the size of the real tiles (Home, Reports, summary strips). */
export function MetricTileSkeleton({ className }: { className?: string }) {
  return <Skeleton className={cn("h-27 rounded-xl", className)} />;
}

/** A chart card: a title line and a plot area of `height`. */
export function ChartSkeleton({ height = "h-40", className }: { height?: string; className?: string }) {
  return (
    <Card className={cn("space-y-3", className)}>
      <Skeleton className="h-4 w-40" />
      <Skeleton className={cn("w-full", height)} />
    </Card>
  );
}

/** A table body for use inside a CardBleed: a header line and `rows` rows of `columns` cells. */
export function TableSkeleton({ columns = 4, rows = 5 }: { columns?: number; rows?: number }) {
  return (
    <div>
        <div className="flex gap-4 border-b border-line px-(--card-padding) py-3">
          {Array.from({ length: columns }, (_, c) => (
            <Skeleton key={c} className="h-3 flex-1" />
          ))}
        </div>
        {Array.from({ length: rows }, (_, r) => (
          <div key={r} className="flex items-center gap-4 border-b border-line-subtle px-(--card-padding) py-3.5 last:border-b-0">
            {Array.from({ length: columns }, (_, c) => (
              <Skeleton key={c} className={cn("h-4 flex-1", c === 0 && "flex-[1.4]")} />
            ))}
          </div>
        ))}
    </div>
  );
}

/** A picture at its real aspect ratio (`aspect-square`, `aspect-video`, `aspect-4/5`). */
export function MediaSkeleton({ ratio = "aspect-square", className }: { ratio?: string; className?: string }) {
  return <Skeleton className={cn("w-full", ratio, className)} />;
}

/** A bordered list card (Contacts): a header strip and `count` rows, the real rows' height. */
export function ListCardSkeleton({ count = 8 }: { count?: number }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center gap-3 border-b border-line px-3 py-2">
        <Skeleton className="size-4 rounded-sm" />
        <Skeleton className="h-3 w-24" />
      </div>
      <div className="divide-y divide-line-subtle">
        {Array.from({ length: count }, (_, i) => (
          <RowSkeleton key={i} className="px-3 py-3" trailing />
        ))}
      </div>
    </Card>
  );
}
