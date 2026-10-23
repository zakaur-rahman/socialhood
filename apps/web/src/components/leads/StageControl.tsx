"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { LeadStage } from "@/lib/api/types";
import { LEAD_STAGES } from "@/lib/leads/stages";
import { cn } from "@/lib/utils";

/**
 * Moves a lead to a stage (GR-18). It shows the current stage and calls ``onChange`` with the one
 * picked; picking the current stage does nothing. Used on a lead's card and in the contact drawer.
 */
export function StageControl({
  value,
  onChange,
  label,
  disabled,
  className,
}: {
  value: LeadStage;
  onChange: (stage: LeadStage) => void;
  /** The accessible name, which says whose stage it is. */
  label: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Select value={value} onValueChange={(next) => next !== value && onChange(next as LeadStage)} disabled={disabled}>
      <SelectTrigger aria-label={label} className={cn("w-full", className)}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {LEAD_STAGES.map((stage) => (
          <SelectItem key={stage.value} value={stage.value}>
            {stage.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
