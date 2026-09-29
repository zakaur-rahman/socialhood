"use client";

import { X } from "lucide-react";
import { useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";

import { addKeywords, KEYWORD_MAX_LENGTH, MAX_KEYWORDS, splitKeywords } from "@/lib/automations/keywords";
import { cn } from "@/lib/utils";

/**
 * UX-SCR-03 keyword chips: Enter or a comma adds what is typed, a pasted list is split, Backspace
 * in the empty field removes the last chip. Duplicates (compared as the matcher compares them)
 * are skipped with a note.
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
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const full = keywords.length >= MAX_KEYWORDS;

  const add = (incoming: string[]) => {
    const result = addKeywords(keywords, incoming);
    if (result.keywords.length !== keywords.length) onChange(result.keywords);
    const added = result.keywords.slice(keywords.length);
    if (result.overflow.length > 0) setNote(`Up to ${MAX_KEYWORDS} keywords. ${result.overflow.length} left out.`);
    else if (result.duplicates.length > 0) {
      setNote(
        result.duplicates.length === 1
          ? `“${result.duplicates[0]}” is already a keyword.`
          : `${result.duplicates.length} were already keywords.`,
      );
    } else if (added.length > 1) setNote(`Added ${added.length} keywords.`);
    else if (added.length === 1) setNote(`Added “${added[0]}”.`);
    else setNote("");
  };

  const commit = () => {
    if (!text.trim()) return;
    add(splitKeywords(text));
    setText("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit();
    } else if (event.key === "Backspace" && text === "" && keywords.length > 0) {
      event.preventDefault();
      const last = keywords[keywords.length - 1];
      onChange(keywords.slice(0, -1));
      setNote(`Removed “${last}”.`);
    }
  };

  const onPaste = (event: ClipboardEvent<HTMLInputElement>) => {
    const pasted = event.clipboardData.getData("text");
    if (!/[,;\t\r\n]/.test(pasted)) return;
    event.preventDefault();
    add(splitKeywords(`${text}${pasted}`));
    setText("");
  };

  const remove = (index: number) => {
    const removed = keywords[index];
    onChange(keywords.filter((_, i) => i !== index));
    setNote(`Removed “${removed}”.`);
    inputRef.current?.focus();
  };

  const describedBy = [`${id}-hint`, error ? `${id}-error` : null].filter(Boolean).join(" ");

  return (
    <div className="space-y-1.5">
      <div
        className={cn(
          "flex min-h-10 flex-wrap items-center gap-1.5 rounded-lg border bg-field px-2 py-1.5 focus-within:border-ring focus-within:bg-raised focus-within:ring-3 focus-within:ring-ring/50",
          error ? "border-danger" : "border-line",
        )}
        onClick={() => inputRef.current?.focus()}
      >
        {keywords.length > 0 ? (
          <ul aria-label="Keywords" className="contents">
            {keywords.map((keyword, index) => (
              <li
                key={`${keyword}-${index}`}
                className="flex items-center gap-1 rounded-full bg-brand-soft py-0.5 pr-1 pl-2.5 text-sm text-brand-fg"
              >
                <span className="max-w-48 truncate">{keyword}</span>
                <button
                  type="button"
                  aria-label={`Remove ${keyword}`}
                  disabled={disabled}
                  onClick={(event) => {
                    event.stopPropagation();
                    remove(index);
                  }}
                  className="grid size-5 place-items-center rounded-full hover:bg-white/10"
                >
                  <X className="size-3.5" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <label htmlFor={id} className="sr-only">
          Add a keyword
        </label>
        <input
          ref={inputRef}
          id={id}
          value={text}
          disabled={disabled || full}
          maxLength={KEYWORD_MAX_LENGTH * 2}
          onChange={(event) => {
            const value = event.target.value;
            // Some phone keyboards never send a "," key event: split on the typed comma instead.
            if (value.includes(",")) {
              add(splitKeywords(value));
              setText("");
            } else setText(value);
          }}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onBlur={commit}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder={full ? "" : keywords.length ? "Add another…" : "Add a keyword…"}
          autoComplete="off"
          className="h-7 min-w-32 flex-1 bg-transparent px-1 text-sm outline-none"
        />
      </div>
      <div className="flex items-start justify-between gap-3 text-xs">
        <p id={`${id}-hint`} className="text-fg-secondary">
          Press Enter or type a comma to add. Paste a list to add several.
        </p>
        <p className="shrink-0 text-fg-secondary tabular-nums">
          {keywords.length} of {MAX_KEYWORDS}
        </p>
      </div>
      {error ? (
        <p id={`${id}-error`} className="text-xs text-danger-fg">
          {error}
        </p>
      ) : null}
      <p role="status" aria-live="polite" className="text-xs text-fg-secondary empty:hidden">
        {note}
      </p>
    </div>
  );
}
