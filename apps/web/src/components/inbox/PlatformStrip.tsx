import { Layers } from "lucide-react";

import { PLATFORM_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Skeleton } from "@/components/ui/skeleton";
import type { Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

export type PlatformChoice = "all" | Platform;

const ACTIVE_BG: Record<PlatformChoice, string> = { all: "bg-brand-gradient", ...PLATFORM_BG };

const COLS: Record<number, string> = { 1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3" };

/**
 * UX-INB-02 (kept from v1): All plus each connected platform. The strip takes the active
 * segment's colour; labels show at ≥ 1280 px, an aria-label otherwise.
 */
export function PlatformStrip({
  platforms,
  value,
  onChange,
  showLabels,
  loading = false,
}: {
  platforms: Platform[];
  value: PlatformChoice;
  onChange: (value: PlatformChoice) => void;
  showLabels: boolean;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-2 p-1" aria-busy="true" aria-label="Loading platforms">
        <Skeleton className="h-11 rounded-tl-lg rounded-br-lg bg-raised" />
        <Skeleton className="h-11 rounded-tl-lg rounded-br-lg bg-raised" />
      </div>
    );
  }
  const choices: PlatformChoice[] = ["all", ...platforms];
  return (
    <div
      role="group"
      aria-label="Platform"
      data-active={value}
      className={cn("grid gap-2 p-1", COLS[choices.length] ?? "grid-cols-3", ACTIVE_BG[value])}
    >
      {choices.map((choice) => {
        const active = choice === value;
        const label = choice === "all" ? "All" : PLATFORM_LABEL[choice];
        return (
          <button
            key={choice}
            type="button"
            aria-pressed={active}
            aria-label={showLabels ? undefined : label}
            onClick={() => onChange(choice)}
            className={cn(
              "flex items-center justify-center gap-2 rounded-tl-lg rounded-br-lg border-2 p-2.5 text-sm font-medium text-white",
              active ? cn(ACTIVE_BG[choice], "border-white/40") : "border-transparent bg-panel hover:bg-field",
            )}
          >
            {choice === "all" ? (
              <Layers className="size-5" aria-hidden />
            ) : (
              <PlatformGlyph platform={choice} className="size-5" />
            )}
            {showLabels ? <span>{label}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
