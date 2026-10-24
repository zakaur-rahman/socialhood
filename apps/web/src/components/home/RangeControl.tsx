"use client";

import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { DatePicker } from "@/components/ui/date-picker";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { OverviewQuery } from "@/lib/api/queries";

import { addDays, checkCustom, choiceOf, MAX_CUSTOM_DAYS, type CustomErrors } from "./range";

/**
 * 7 days / 30 days / Custom. Custom opens two date pickers (local days in the workspace's time
 * zone, up to today, at most 90 days) and applies them together; clicking Custom again edits them.
 */
export function RangeControl({
  value,
  today,
  onChange,
}: {
  value: OverviewQuery;
  /** Today in the workspace's time zone, YYYY-MM-DD. */
  today: string;
  onChange: (query: OverviewQuery) => void;
}) {
  const [open, setOpen] = useState(false);
  const customRef = useRef<HTMLButtonElement>(null);
  const choice = choiceOf(value);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div>
          <ToggleGroup
            aria-label="Period"
            value={choice}
            onValueChange={(next) => {
              if (next === "7d" || next === "30d") onChange({ range: next });
            }}
            className="w-auto"
          >
            <ToggleGroupItem value="7d">7 days</ToggleGroupItem>
            <ToggleGroupItem value="30d">30 days</ToggleGroupItem>
            <ToggleGroupItem ref={customRef} value="custom" onClick={() => setOpen(true)}>
              Custom
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </PopoverAnchor>
      <PopoverContent
        align="end"
        // Keep 16 px from the viewport edge (the popover sat 3 px from it at 375).
        collisionPadding={16}
        className="w-[min(20rem,calc(100vw-2rem))] p-4"
        aria-label="Custom period"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          customRef.current?.focus();
        }}
      >
        <CustomRangeForm
          initial={"from" in value ? value : { from: addDays(today, -6), to: today }}
          today={today}
          onApply={(range) => {
            onChange(range);
            setOpen(false);
          }}
          onCancel={() => setOpen(false)}
        />
      </PopoverContent>
    </Popover>
  );
}

function CustomRangeForm({
  initial,
  today,
  onApply,
  onCancel,
}: {
  initial: { from: string; to: string };
  today: string;
  onApply: (range: { from: string; to: string }) => void;
  onCancel: () => void;
}) {
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [errors, setErrors] = useState<CustomErrors | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const problems = checkCustom(from, to, today);
    setErrors(problems);
    if (!problems) onApply({ from, to });
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-3" aria-label="Custom period">
      <p className="text-xs text-fg-secondary">Up to {MAX_CUSTOM_DAYS} days, ending today at the latest.</p>
      <div className="grid grid-cols-2 gap-3">
        <Field id="home-range-from">
          <FieldLabel>From</FieldLabel>
          <DatePicker
            value={from}
            max={to || today}
            min={to ? addDays(to, -(MAX_CUSTOM_DAYS - 1)) : undefined}
            today={today}
            jumpMonths
            onChange={setFrom}
          />
          <FieldError>{errors?.from}</FieldError>
        </Field>
        <Field id="home-range-to">
          <FieldLabel>To</FieldLabel>
          <DatePicker value={to} min={from || undefined} max={today} today={today} jumpMonths onChange={setTo} />
          <FieldError>{errors?.to}</FieldError>
        </Field>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">Apply</Button>
      </div>
    </form>
  );
}
