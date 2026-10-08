import { Badge } from "@/components/ui/badge";
import type { ReplyWindow } from "@/lib/api/types";
import { windowChip } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

/**
 * UX-INB-05, beside the name (C-063): "Window: 18h left" neutral, amber under 2 h, red "Window
 * closed" after; Human Agent and template only as before. A status Badge (11 px, 20 px tall) in
 * the window's tone. `compact` (the handle line of a narrow thread header) shows "18h left": the
 * "Window:" or "Human Agent:" part is for screen readers only, and the rest truncates when the line
 * is short (in a span of its own: a badge is a flex box, whose bare text can't end in an ellipsis).
 */
export function ReplyWindowChip({
  window,
  now,
  compact = false,
  className,
}: {
  window: ReplyWindow;
  now: Date;
  compact?: boolean;
  className?: string;
}) {
  const chip = windowChip(window, now);
  // "Window: " or "Human Agent: ", read but not shown in the compact chip.
  const cut = chip.label.indexOf(": ") + 2;
  const hidden = cut > 1 ? chip.label.slice(0, cut) : "";
  return (
    <Badge tone={chip.tone} className={cn("tabular-nums", className)} data-state={window.state}>
      {compact ? (
        <>
          {hidden ? <span className="sr-only">{hidden}</span> : null}
          <span className="min-w-0 truncate">{chip.label.slice(hidden.length)}</span>
        </>
      ) : (
        chip.label
      )}
    </Badge>
  );
}
