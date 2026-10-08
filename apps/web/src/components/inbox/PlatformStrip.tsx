import { Layers } from "lucide-react";

import { PLATFORM_BG } from "@/components/connections/PlatformGlyph";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

export type PlatformChoice = "all" | Platform;

/**
 * UX-INB-02 as the segmented control (C-063, DESIGN_SYSTEM §8.2): All plus each connected platform,
 * labelled at every width, sharing the track's width equally; a platform's segment carries its
 * colour as a dot. The chosen segment is the primitive's neutral one, `raised` with `brand-fg`
 * text, like every other segmented control (D-15 item 1).
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
        <Skeleton className="h-9 rounded-lg" />
      </div>
    );
  }
  const choices: PlatformChoice[] = ["all", ...platforms];
  return (
    <div className="px-3 pt-3">
      <ToggleGroup
        aria-label="Platform"
        size="sm"
        value={value}
        onValueChange={(choice) => onChange(choice as PlatformChoice)}
        data-active={value}
      >
        {choices.map((choice) => (
          <ToggleGroupItem key={choice} value={choice} className="min-w-0">
            {choice === "all" ? (
              <Layers className="size-3.5 shrink-0" aria-hidden />
            ) : (
              <span className={cn("size-2 shrink-0 rounded-full", PLATFORM_BG[choice])} aria-hidden />
            )}
            <span className="truncate">{choice === "all" ? "All" : PLATFORM_LABEL[choice]}</span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
