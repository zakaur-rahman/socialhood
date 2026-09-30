import { Layers } from "lucide-react";

import { PLATFORM_BG } from "@/components/connections/PlatformGlyph";
import { Skeleton } from "@/components/ui/skeleton";
import type { Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

export type PlatformChoice = "all" | Platform;

const COLS: Record<number, string> = { 1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3" };

/**
 * UX-INB-02, restyled as a segmented control (C-063): All plus each connected platform, labelled
 * at every width; a platform's segment carries its colour as a dot.
 */
export function PlatformStrip({
  platforms,
  value,
  onChange,
  loading = false,
}: {
  platforms: Platform[];
  value: PlatformChoice;
  onChange: (value: PlatformChoice) => void;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="px-3 pt-3" aria-busy="true" aria-label="Loading platforms">
        <Skeleton className="h-9 rounded-lg bg-raised" />
      </div>
    );
  }
  const choices: PlatformChoice[] = ["all", ...platforms];
  return (
    <div className="px-3 pt-3">
      <div
        role="group"
        aria-label="Platform"
        data-active={value}
        className={cn("grid gap-1 rounded-lg border border-line bg-field p-1", COLS[choices.length] ?? "grid-cols-3")}
      >
        {choices.map((choice) => {
          const active = choice === value;
          return (
            <button
              key={choice}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(choice)}
              className={cn(
                "flex min-w-0 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium",
                active ? "bg-brand text-white shadow-sm" : "text-fg-secondary hover:bg-white/5 hover:text-fg",
              )}
            >
              {choice === "all" ? (
                <Layers className="size-3.5 shrink-0" aria-hidden />
              ) : (
                <span className={cn("size-2 shrink-0 rounded-full", PLATFORM_BG[choice], active && "ring-2 ring-white/40")} aria-hidden />
              )}
              <span className="truncate">{choice === "all" ? "All" : PLATFORM_LABEL[choice]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
