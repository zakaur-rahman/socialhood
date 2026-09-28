import type { ReplyWindow } from "@/lib/api/types";
import { TONE_CLASS, windowChip } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

/** UX-INB-05: "Window: 18h left", warning under 2 h, Human Agent, closed, template only. */
export function ReplyWindowChip({ window, now }: { window: ReplyWindow; now: Date }) {
  const chip = windowChip(window, now);
  return (
    <span
      className={cn(
        "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap tabular-nums",
        chip.tone === "neutral" ? "text-fg-secondary" : TONE_CLASS[chip.tone],
      )}
      data-tone={chip.tone}
      data-state={window.state}
    >
      {chip.label}
    </span>
  );
}
