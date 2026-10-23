"use client";

import { useId, type ReactNode } from "react";

import { fieldControlClass } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * A labelled native select in the field look. The flow editor has many small choices per card
 * (the kind of answer, a tag, a field, an operator); a native control opens the platform's own
 * picker on a phone and is the simplest thing a screen reader and a keyboard already know.
 */
export function NativeSelect({
  label,
  value,
  onChange,
  children,
  invalid,
  describedBy,
  className,
  hideLabel = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
  invalid?: boolean;
  describedBy?: string;
  className?: string;
  hideLabel?: boolean;
}) {
  const id = useId();
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id} className={hideLabel ? "sr-only" : undefined}>
        {label}
      </Label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={invalid ? true : undefined}
        aria-describedby={describedBy}
        className={cn(fieldControlClass, "h-9 py-1 pointer-coarse:min-h-10")}
      >
        {children}
      </select>
    </div>
  );
}
