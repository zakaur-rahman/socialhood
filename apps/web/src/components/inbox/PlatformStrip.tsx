import { Layers } from "lucide-react";

import { PLATFORM_LOGO_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

export type PlatformChoice = "all" | Platform;

/**
 * UX-INB-02 as the segmented control (C-063, DESIGN_SYSTEM §8.2): All plus each connected platform,
 * sharing the track's width equally. A platform's segment shows its mark on its own colours, named
 * for screen readers and on hover (owner, C-188); names were cut to "Insta…" in the list pane. The chosen segment is the primitive's neutral one, `raised` with `brand-fg`
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
      <div className="px-3 pt-3" role="status" aria-busy="true" aria-label="Loading platforms">
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
        {choices.map((choice) =>
          choice === "all" ? (
            <ToggleGroupItem key={choice} value={choice} className="min-w-0">
              <Layers className="size-3.5 shrink-0" aria-hidden />
              <span className="truncate">All</span>
            </ToggleGroupItem>
          ) : (
            <ToggleGroupItem key={choice} value={choice} className="min-w-0" title={PLATFORM_LABEL[choice]}>
              <span
                className={cn("grid size-5 shrink-0 place-items-center rounded-md text-on-brand", PLATFORM_LOGO_BG[choice])}
                aria-hidden
              >
                <PlatformGlyph platform={choice} className="size-3" />
              </span>
              <span className="sr-only">{PLATFORM_LABEL[choice]}</span>
            </ToggleGroupItem>
          ),
        )}
      </ToggleGroup>
    </div>
  );
}
