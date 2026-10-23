"use client";

import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ADDABLE, type StepKind } from "@/lib/automations/flow";

/**
 * The "Add step" menu: Send, Ask, Branch, Action, Delay, Split, End (the step kinds the flow engine
 * runs; the AI reply is chosen above the steps). Disabled with its reason when the plan's cap is
 * reached.
 */
export function KindMenu({
  onPick,
  label = "Add step",
  ariaLabel,
  disabledReason,
  variant = "secondary",
}: {
  onPick: (kind: Exclude<StepKind, "ai">) => void;
  label?: string;
  ariaLabel?: string;
  disabledReason?: string | null;
  variant?: "secondary" | "outline";
}) {
  if (disabledReason) {
    return (
      <Button variant={variant} size="sm" disabled aria-label={ariaLabel} title={disabledReason}>
        <Plus aria-hidden /> {label}
      </Button>
    );
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant={variant} size="sm" aria-label={ariaLabel}>
          <Plus aria-hidden /> {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {ADDABLE.map((item) => (
          <DropdownMenuItem key={item.kind} onSelect={() => onPick(item.kind)} className="flex-col items-start gap-0">
            <span className="font-medium">{item.label}</span>
            <span className="text-xs text-fg-secondary">{item.hint}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
