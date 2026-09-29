"use client";

import { X } from "lucide-react";
import { useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

/**
 * A list of short phrases as chips (brand voice do and don't lists, escalation phrases): Enter
 * adds what is typed, a pasted list is split by lines, Backspace in the empty field removes the
 * last chip. Commas stay inside a phrase. Duplicates (ignoring case) are skipped with a note.
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
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const full = items.length >= max;

  const add = (incoming: string[]) => {
    const next = [...items];
    const seen = new Set(items.map((item) => item.toLowerCase()));
    let duplicates = 0;
    let overflow = 0;
    for (const raw of incoming) {
      const item = raw.trim().slice(0, maxLength);
      if (!item) continue;
      if (seen.has(item.toLowerCase())) {
        duplicates += 1;
        continue;
      }
      if (next.length >= max) {
        overflow += 1;
        continue;
      }
      seen.add(item.toLowerCase());
      next.push(item);
    }
    if (next.length !== items.length) onChange(next);
    const added = next.length - items.length;
    if (overflow > 0) setNote(`Up to ${max}. ${overflow} left out.`);
    else if (duplicates > 0) setNote(duplicates === 1 ? "That one is already in the list." : `${duplicates} were already in the list.`);
    else if (added > 1) setNote(`Added ${added}.`);
    else if (added === 1) setNote(`Added “${next[next.length - 1]}”.`);
    else setNote("");
  };

  const commit = () => {
    if (!text.trim()) return;
    add([text]);
    setText("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Backspace" && text === "" && items.length > 0) {
      event.preventDefault();
      const last = items[items.length - 1];
      onChange(items.slice(0, -1));
      setNote(`Removed “${last}”.`);
    }
  };

  const onPaste = (event: ClipboardEvent<HTMLInputElement>) => {
    const pasted = event.clipboardData.getData("text");
    if (!/[\r\n]/.test(pasted)) return;
    event.preventDefault();
    add(`${text}${pasted}`.split(/[\r\n]+/));
    setText("");
  };

  const remove = (index: number) => {
    const removed = items[index];
    onChange(items.filter((_, i) => i !== index));
    setNote(`Removed “${removed}”.`);
    inputRef.current?.focus();
  };

  return (
    <div className="space-y-1.5">
      <div
        className="flex min-h-10 flex-wrap items-center gap-1.5 rounded-lg border border-line bg-field px-2 py-1.5 focus-within:border-ring focus-within:bg-raised focus-within:ring-3 focus-within:ring-ring/50"
        onClick={() => inputRef.current?.focus()}
      >
        {items.length > 0 ? (
          <ul aria-label={label} className="contents">
            {items.map((item, index) => (
              <li
                key={`${item}-${index}`}
                className="flex max-w-full items-center gap-1 rounded-full bg-brand-soft py-0.5 pr-1 pl-2.5 text-sm text-brand-fg"
              >
                <span className="truncate">{item}</span>
                <button
                  type="button"
                  aria-label={`Remove ${item}`}
                  disabled={disabled}
                  onClick={(event) => {
                    event.stopPropagation();
                    remove(index);
                  }}
                  className="grid size-5 shrink-0 place-items-center rounded-full hover:bg-white/10"
                >
                  <X className="size-3.5" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <label htmlFor={id} className="sr-only">
          Add to {label}
        </label>
        <input
          ref={inputRef}
          id={id}
          value={text}
          disabled={disabled || full}
          maxLength={maxLength}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onBlur={commit}
          aria-describedby={`${id}-hint`}
          placeholder={full ? "" : placeholder}
          autoComplete="off"
          className={cn("h-7 min-w-40 flex-1 bg-transparent px-1 text-sm outline-none")}
        />
      </div>
      <div className="flex items-start justify-between gap-3 text-xs">
        <p id={`${id}-hint`} className="text-fg-secondary">
          {hint ?? "Press Enter to add. Paste a list to add several."}
        </p>
        <p className="shrink-0 text-fg-secondary tabular-nums">
          {items.length} of {max}
        </p>
      </div>
      <p role="status" aria-live="polite" className="text-xs text-fg-secondary empty:hidden">
        {note}
      </p>
    </div>
  );
}
