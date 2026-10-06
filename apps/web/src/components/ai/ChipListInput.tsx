"use client";

import { ChipInput } from "@/components/ui/chip-input";

/**
 * A list of short phrases as chips on ChipInput (brand voice do and don't lists): Enter adds what
 * is typed, a pasted list is split by lines, Backspace in the empty field removes the last chip.
 * Commas stay inside a phrase. Duplicates (ignoring case) are skipped with a note.
 */
export function ChipListInput({
  id,
  label,
  items,
  onChange,
  max = 20,
  maxLength = 120,
  placeholder = "Type and press Enter",
  hint,
  disabled = false,
}: {
  id: string;
  /** The field's name, e.g. "Always"; the input is labelled "Add to {label}". */
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  max?: number;
  maxLength?: number;
  placeholder?: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <ChipInput
      id={id}
      value={items}
      onValueChange={onChange}
      inputLabel={`Add to ${label}`}
      listLabel={label}
      max={max}
      maxLength={maxLength}
      placeholder={placeholder}
      hint={hint}
      disabled={disabled}
    />
  );
}
