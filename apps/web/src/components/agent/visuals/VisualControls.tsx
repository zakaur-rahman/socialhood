import { useId } from "react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  controlGate,
  controlHints,
  costWords,
  PLATFORM_OPTIONS,
  RANGE_OPTIONS,
  type CreditsNow,
  type Selection,
} from "@/lib/agent/controls";
import type { RunHints } from "@/lib/api/types";

/**
 * VIS-11: range (7, 30, 90 days) and platform under a visual. Choosing one asks the same question
 * again in this thread with the new choice (a structured follow-up, never a data query from the
 * browser), so each change is a run and costs a run's credits. The cost is said before the choice;
 * when the plan has no credits or too few, the controls are off and the line says why.
 */
export function VisualControls({
  selection,
  credits,
  now,
  busy,
  onChange,
}: {
  selection: Selection;
  credits: CreditsNow;
  now?: Date;
  /** A question is being sent, or another run in the thread is working. */
  busy?: boolean;
  onChange: (hints: RunHints) => void;
}) {
  const noteId = useId();
  const gate = controlGate(credits, now);
  const disabled = busy || !gate.ok;
  return (
    <div className="space-y-1.5" data-testid="visual-controls">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <ToggleGroup
          variant="chips"
          aria-label="Range"
          aria-describedby={noteId}
          value={selection.rangeDays === null ? "" : String(selection.rangeDays)}
          disabled={disabled}
          onValueChange={(value) => onChange(controlHints(selection, { rangeDays: Number(value) as 7 | 30 | 90 }))}
        >
          {RANGE_OPTIONS.map((days) => (
            <ToggleGroupItem key={days} value={String(days)} aria-label={`Last ${days} days`}>
              {days} days
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <ToggleGroup
          variant="chips"
          aria-label="Platform"
          aria-describedby={noteId}
          value={selection.platform ?? ""}
          disabled={disabled}
          onValueChange={(value) => onChange(controlHints(selection, { platform: value as Selection["platform"] }))}
        >
          {PLATFORM_OPTIONS.map((option) => (
            <ToggleGroupItem key={option.value} value={option.value}>
              {option.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <p id={noteId} className="text-xs text-fg-secondary" data-testid="controls-note">
        {gate.ok ? `Changing this asks again. ${costWords}.` : gate.reason}
      </p>
    </div>
  );
}
