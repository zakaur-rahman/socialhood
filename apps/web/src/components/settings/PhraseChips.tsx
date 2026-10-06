"use client";

import { ChipInput, type ChipInputMessages } from "@/components/ui/chip-input";

import { SectionLabel } from "./SettingsCard";

const MESSAGES: Partial<ChipInputMessages> = {
  counter: (count, max) => `${count} of ${max} used`,
};

/**
 * Phrases as removable chips in an add field, with "n of N used" (C-066, Settings → AI's
 * escalation phrases), on ChipInput. Enter or Add adds what is typed; a duplicate (any case) is
 * skipped with a note; at the maximum the field takes no more text.
 */
export function PhraseChips({
  id,
  label,
  items,
  onChange,
  max,
  maxLength,
  placeholder,
  hint,
  disabled = false,
}: {
  id: string;
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  max: number;
  maxLength: number;
  placeholder: string;
  hint: string;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-3">
      <SectionLabel>{label}</SectionLabel>
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
        addButton
        disabled={disabled}
        messages={MESSAGES}
      />
    </div>
  );
}
