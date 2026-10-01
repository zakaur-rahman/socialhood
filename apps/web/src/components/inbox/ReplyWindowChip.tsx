import type { ReplyWindow } from "@/lib/api/types";
import { TONE_CLASS, windowChip } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

/**
 * UX-INB-05, beside the name (C-063): "Window: 18h left" neutral, amber under 2 h, red "Window
 * closed" after; Human Agent and template only as before. `compact` (the handle line of a narrow
 * thread header) shows "18h left": the "Window:" or "Human Agent:" part is for screen readers only.
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
  const split = compact ? chip.label.indexOf(": ") + 2 : 0;
  return (
    <span
      className={cn(
        "shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap tabular-nums",
        chip.tone === "neutral" ? "border border-line bg-field text-fg-secondary" : TONE_CLASS[chip.tone],
        className,
      )}
      data-tone={chip.tone}
      data-state={window.state}
    >
      {split > 1 ? (
        <>
          <span className="sr-only">{chip.label.slice(0, split)}</span>
          {chip.label.slice(split)}
        </>
      ) : (
        chip.label
      )}
    </span>
  );
}
