"use client";

import { ChipInput, type ChipInputMessages } from "@/components/ui/chip-input";
import { KEYWORD_MAX_LENGTH, MAX_KEYWORDS, normalizeKeyword, splitKeywords } from "@/lib/automations/keywords";

const MESSAGES: Partial<ChipInputMessages> = {
  added: (added) => (added.length === 1 ? `Added “${added[0]}”.` : `Added ${added.length} keywords.`),
  duplicates: (duplicates) =>
    duplicates.length === 1 ? `“${duplicates[0]}” is already a keyword.` : `${duplicates.length} were already keywords.`,
  overflow: (count, max) => `Up to ${max} keywords. ${count} left out.`,
};

/**
 * UX-SCR-03 keyword chips on ChipInput: Enter or a comma adds what is typed, a pasted list is
 * split, Backspace in the empty field removes the last chip. Duplicates (compared as the matcher
 * compares them) are skipped with a note.
 */
export function KeywordInput({
  id,
  keywords,
  onChange,
  error,
  disabled = false,
}: {
  id: string;
  keywords: string[];
  onChange: (keywords: string[]) => void;
  /** An activation or save error for the keywords field. */
  error?: string | null;
  disabled?: boolean;
}) {
  return (
    <ChipInput
      id={id}
      value={keywords}
      onValueChange={onChange}
      inputLabel="Add a keyword"
      listLabel="Keywords"
      separator="comma"
      split={splitKeywords}
      normalize={normalizeKeyword}
      max={MAX_KEYWORDS}
      maxLength={KEYWORD_MAX_LENGTH}
      inputMaxLength={KEYWORD_MAX_LENGTH * 2}
      placeholder={keywords.length ? "Add another…" : "Add a keyword…"}
      error={error}
      disabled={disabled}
      messages={MESSAGES}
    />
  );
}
