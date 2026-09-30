import type { ReplyWindow } from "@/lib/api/types";
import { TONE_CLASS, windowChip } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

/**
 * UX-INB-05, beside the name (C-063): "Window: 18h left" neutral, amber under 2 h, red "Window
 * closed" after; Human Agent and template only as before.
 */
export function ReplyWindowChip({ window, now }: { window: ReplyWindow; now: Date }) {
  const chip = windowChip(window, now);
  return (
    <span
      className={cn(
        "shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap tabular-nums",
        chip.tone === "neutral" ? "border border-line bg-field text-fg-secondary" : TONE_CLASS[chip.tone],
      )}
      data-tone={chip.tone}
      data-state={window.state}
    >
      {chip.label}
    </span>
  );
}
