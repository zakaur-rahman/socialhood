"use client";

import { MessageSquarePlus, X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";

import { SectionLabel } from "./SettingsCard";

/**
 * Phrases as removable chips under an add field, with "n of N used" beside the label (C-066,
 * Settings → AI's escalation phrases). Enter or Add adds what is typed; a duplicate (any case)
 * is skipped with a note; at the maximum the field is disabled.
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
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const full = items.length >= max;

  const add = () => {
    const phrase = text.trim().slice(0, maxLength);
    if (!phrase) return;
    if (items.some((item) => item.toLowerCase() === phrase.toLowerCase())) {
      setNote("That one is already in the list.");
      return;
    }
    if (full) {
      setNote(`Up to ${max}.`);
      return;
    }
    onChange([...items, phrase]);
    setText("");
    setNote(`Added “${phrase}”.`);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      add();
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <SectionLabel id={`${id}-label`}>{label}</SectionLabel>
        <p className="shrink-0 text-xs text-fg-secondary tabular-nums">
          {items.length} of {max} used
        </p>
      </div>
      <div className="flex min-h-11 items-center gap-2 rounded-xl border border-line bg-field py-1 pr-1 pl-3 focus-within:ring-2 focus-within:ring-brand">
        <MessageSquarePlus className="size-4 shrink-0 text-fg-secondary" aria-hidden />
        <label htmlFor={id} className="sr-only">
          Add to {label}
        </label>
        <input
          id={id}
          value={text}
          maxLength={maxLength}
          disabled={disabled || full}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={full ? `All ${max} used` : placeholder}
          aria-describedby={`${id}-hint`}
          autoComplete="off"
          className="h-9 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-fg-disabled"
        />
        <Button
          type="button"
          variant="secondary"
          className="min-h-9 px-3 text-brand-fg"
          disabled={disabled || full || !text.trim()}
          onClick={add}
        >
          Add
        </Button>
      </div>
      {items.length > 0 ? (
        <ul aria-labelledby={`${id}-label`} className="flex flex-wrap gap-2">
          {items.map((item) => (
            <li
              key={item}
              className="flex max-w-full items-center gap-1 rounded-lg border border-line bg-raised py-1 pr-1 pl-3 text-sm"
            >
              <span className="truncate">{item}</span>
              <button
                type="button"
                aria-label={`Remove ${item}`}
                disabled={disabled}
                onClick={() => {
                  onChange(items.filter((other) => other !== item));
                  setNote(`Removed “${item}”.`);
                }}
                className="grid size-8 shrink-0 place-items-center rounded-md text-fg-secondary outline-none hover:bg-white/10 hover:text-fg focus-visible:ring-2 focus-visible:ring-brand"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p id={`${id}-hint`} className="text-xs text-fg-secondary">
        {hint}
      </p>
      <p role="status" aria-live="polite" className="text-xs text-fg-secondary empty:hidden">
        {note}
      </p>
    </div>
  );
}
