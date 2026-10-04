"use client"

import * as React from "react"
import { XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useFieldControl } from "@/components/ui/field"
import { fieldControlClass } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/**
 * ChipInput: a short list (keywords, phrases) as chips inside one field (DESIGN_SYSTEM §8.2,
 * UI-ISS-040). It replaces three copies that differed only in validation and counters.
 *
 * - **Adding:** Enter adds what is typed; with `separator="comma"` a typed comma adds too (also on
 *   phone keyboards that never send a "," key event). A pasted list is split: by lines, or with
 *   `"comma"` by commas, semicolons, tabs and lines. Leaving the field adds what is typed, unless
 *   the field has an Add button (`addButton`), which then is the way to add.
 * - **Removing:** each chip's × (a 24 px target, 40 px on coarse pointers, where chips are 32 px
 *   tall and rows 8 px apart so neighbouring targets don't overlap), or Backspace in the empty field.
 * - **Validation:** items are trimmed (inner spaces collapsed) and cut to `maxLength`; duplicates,
 *   compared through `normalize` (case-insensitive by default), are skipped; at `max` the field
 *   stops taking text. A polite status line says what happened; the counter shows "n of max".
 * - **Look:** the text-field recipe (`fieldControlClass`) on the box, so it matches Input. The
 *   focus outline sits on the box while its text field has focus (`has-[input:focus-visible]:`);
 *   16 px text below `md` (no iOS zoom). `error`, or a Field's FieldError, turns the edge danger.
 * - **Field:** inside a Field, the text field takes the Field's id, description, error and
 *   disabled state, and the FieldLabel names it; leave `inputLabel` out there.
 *
 *   <ChipInput value={keywords} onValueChange={setKeywords} inputLabel="Add a keyword"
 *     listLabel="Keywords" separator="comma" max={50} />
 */

type ChipInputSeparator = "line" | "comma"

/** What typed or pasted text splits on. */
const SPLIT: Record<ChipInputSeparator, RegExp> = {
  line: /[\r\n]+/,
  comma: /[,;\t\r\n]+/,
}

/** A paste containing one of these is a list. */
const LIST_PASTE: Record<ChipInputSeparator, RegExp> = {
  line: /[\r\n]/,
  comma: /[,;\t\r\n]/,
}

const DEFAULT_HINT: Record<ChipInputSeparator, string> = {
  line: "Press Enter to add. Paste a list to add several.",
  comma: "Press Enter or type a comma to add. Paste a list to add several.",
}

type ChipInputMessages = {
  /** One or more items were added. */
  added: (items: string[]) => string
  /** Nothing new was added because these were already in the list. */
  duplicates: (items: string[]) => string
  /** `count` items were left out because the list holds `max`. */
  overflow: (count: number, max: number) => string
  removed: (item: string) => string
  counter: (count: number, max: number) => string
}

const DEFAULT_MESSAGES: ChipInputMessages = {
  added: (items) => (items.length === 1 ? `Added “${items[0]}”.` : `Added ${items.length}.`),
  duplicates: (items) =>
    items.length === 1 ? "That one is already in the list." : `${items.length} were already in the list.`,
  overflow: (count, max) => `Up to ${max}. ${count} left out.`,
  removed: (item) => `Removed “${item}”.`,
  counter: (count, max) => `${count} of ${max}`,
}

const caseInsensitive = (item: string) => item.toLowerCase()

function splitBy(separator: ChipInputSeparator) {
  return (text: string) =>
    text
      .split(SPLIT[separator])
      .map((part) => part.replace(/\s+/g, " ").trim())
      .filter(Boolean)
}

type AddResult = { items: string[]; added: string[]; duplicates: string[]; overflow: string[] }

function addItems(
  existing: string[],
  incoming: string[],
  { max, maxLength, normalize }: { max: number; maxLength: number; normalize: (item: string) => string }
): AddResult {
  const seen = new Set(existing.map(normalize))
  const items = [...existing]
  const duplicates: string[] = []
  const overflow: string[] = []
  for (const raw of incoming) {
    const item = raw.trim().slice(0, maxLength).trim()
    if (!item) continue
    const key = normalize(item)
    if (seen.has(key)) {
      duplicates.push(item)
      continue
    }
    if (items.length >= max) {
      overflow.push(item)
      continue
    }
    seen.add(key)
    items.push(item)
  }
  return { items, added: items.slice(existing.length), duplicates, overflow }
}

type ChipInputProps = {
  /** The text field's id; inside a Field, leave it out (or use the Field's). */
  id?: string
  value: string[]
  onValueChange: (value: string[]) => void
  /** The text field's name, visually hidden ("Add a keyword"). Inside a Field, FieldLabel names it. */
  inputLabel?: string
  /** The chip list's name ("Keywords"). */
  listLabel?: string
  /** How many items the list holds (default 20). */
  max?: number
  /** Each item is cut to this many characters (default 120). */
  maxLength?: number
  /** How many characters the text field takes; defaults to `maxLength`. */
  inputMaxLength?: number
  /** `line` (default): phrases, commas stay inside an item. `comma`: keywords and tags. */
  separator?: ChipInputSeparator
  /** How typed or pasted text becomes items; defaults to the separator's split. */
  split?: (text: string) => string[]
  /** Duplicates are items with the same key (default: lower case). */
  normalize?: (item: string) => string
  placeholder?: string
  /** Under the field, beside the counter. Defaults to how to add; `null` hides it. */
  hint?: React.ReactNode
  /** An error for the list (a save or activation error), linked to the text field. */
  error?: React.ReactNode
  /** Shows an Add button in the field; then leaving the field doesn't add what is typed. */
  addButton?: boolean
  /** Overrides for the status and counter wording. */
  messages?: Partial<ChipInputMessages>
  disabled?: boolean
  className?: string
  "aria-describedby"?: string
  "aria-invalid"?: React.AriaAttributes["aria-invalid"]
}

function ChipInput({
  id: idProp,
  value,
  onValueChange,
  inputLabel,
  listLabel,
  max = 20,
  maxLength = 120,
  inputMaxLength,
  separator = "line",
  split,
  normalize = caseInsensitive,
  placeholder,
  hint,
  error,
  addButton = false,
  messages: messageOverrides,
  disabled: disabledProp,
  className,
  "aria-describedby": describedByProp,
  "aria-invalid": invalidProp,
}: ChipInputProps) {
  const generatedId = React.useId()
  const baseId = idProp ?? generatedId
  const hintContent = hint === undefined ? DEFAULT_HINT[separator] : hint
  const hintId = hintContent ? `${baseId}-hint` : undefined
  const countId = `${baseId}-count`
  const errorId = error ? `${baseId}-error` : undefined

  const own = {
    id: baseId,
    "aria-describedby": [describedByProp, hintId, countId, errorId].filter(Boolean).join(" "),
    "aria-invalid": invalidProp ?? (error ? true : undefined),
    disabled: disabledProp,
  }
  const control = { ...own, ...useFieldControl({ ...own, id: idProp }) }
  const disabled = Boolean(control.disabled)
  const invalid = control["aria-invalid"] === true || control["aria-invalid"] === "true"

  const [text, setText] = React.useState("")
  const [note, setNote] = React.useState("")
  const inputRef = React.useRef<HTMLInputElement>(null)
  const refocus = React.useRef(false)
  const full = value.length >= max
  const messages = { ...DEFAULT_MESSAGES, ...messageOverrides }
  const toItems = split ?? splitBy(separator)

  // After a chip is removed, focus returns to the text field once it is enabled again.
  React.useEffect(() => {
    if (!refocus.current) return
    refocus.current = false
    inputRef.current?.focus()
  })

  const add = (incoming: string[]) => {
    const result = addItems(value, incoming, { max, maxLength, normalize })
    if (result.added.length > 0) onValueChange(result.items)
    if (result.overflow.length > 0) setNote(messages.overflow(result.overflow.length, max))
    else if (result.duplicates.length > 0) setNote(messages.duplicates(result.duplicates))
    else if (result.added.length > 0) setNote(messages.added(result.added))
    else setNote("")
  }

  const commit = () => {
    if (!text.trim()) return
    add(toItems(text))
    setText("")
  }

  const remove = (index: number) => {
    const removed = value[index]
    onValueChange(value.filter((_, i) => i !== index))
    setNote(messages.removed(removed))
    refocus.current = true
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.nativeEvent.isComposing) return
    if (event.key === "Enter" || (separator === "comma" && event.key === ",")) {
      event.preventDefault()
      commit()
    } else if (event.key === "Backspace" && text === "" && value.length > 0) {
      event.preventDefault()
      remove(value.length - 1)
    }
  }

  const onChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next = event.target.value
    // Some phone keyboards never send a "," key event: split on the typed comma instead.
    if (separator === "comma" && next.includes(",")) {
      add(toItems(next))
      setText("")
    } else setText(next)
  }

  const onPaste = (event: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = event.clipboardData.getData("text")
    if (!LIST_PASTE[separator].test(pasted)) return
    event.preventDefault()
    add(toItems(`${text}${pasted}`))
    setText("")
  }

  return (
    <div data-slot="chip-input" className={cn("flex flex-col gap-1.5", className)}>
      <div
        data-slot="chip-input-control"
        data-disabled={disabled ? "true" : undefined}
        data-invalid={invalid ? "true" : undefined}
        onClick={() => inputRef.current?.focus()}
        className={cn(
          fieldControlClass,
          "flex min-h-10 cursor-text flex-wrap items-center gap-1.5 px-2 py-1 pointer-coarse:gap-y-2",
          "has-[input:focus-visible]:border-ring has-[input:focus-visible]:bg-raised has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-ring",
          "data-invalid:border-danger data-disabled:cursor-not-allowed data-disabled:opacity-50"
        )}
      >
        {value.length > 0 ? (
          <ul aria-label={listLabel} className="contents">
            {value.map((item, index) => (
              <li
                key={`${item}-${index}`}
                data-slot="chip"
                className="flex max-w-full min-w-0 items-center gap-1 rounded-full bg-brand-soft py-0.5 pr-1 pl-2.5 text-sm text-brand-fg pointer-coarse:min-h-8"
              >
                <span className="min-w-0 truncate">{item}</span>
                <button
                  type="button"
                  aria-label={`Remove ${item}`}
                  disabled={disabled}
                  onClick={(event) => {
                    event.stopPropagation()
                    remove(index)
                  }}
                  className="relative grid size-5 shrink-0 place-items-center rounded-full transition-[background-color] duration-fast ease-standard after:absolute after:-inset-0.5 hover:bg-hover disabled:pointer-events-none pointer-coarse:after:-inset-2.5"
                >
                  <XIcon className="size-3.5" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {inputLabel ? (
          <label htmlFor={control.id} className="sr-only">
            {inputLabel}
          </label>
        ) : null}
        <input
          ref={inputRef}
          {...control}
          aria-describedby={control["aria-describedby"] || undefined}
          disabled={disabled || full}
          value={text}
          maxLength={inputMaxLength ?? maxLength}
          onChange={onChange}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onBlur={addButton ? undefined : commit}
          placeholder={full ? undefined : placeholder}
          autoComplete="off"
          className="h-7 min-w-32 flex-1 bg-transparent px-1 text-fg placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed"
        />
        {addButton ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={disabled || full || !text.trim()}
            onClick={(event) => {
              event.stopPropagation()
              commit()
              inputRef.current?.focus()
            }}
          >
            Add
          </Button>
        ) : null}
      </div>
      <div className="flex items-start gap-3 text-xs text-fg-secondary">
        {hintContent ? <p id={hintId}>{hintContent}</p> : null}
        <p id={countId} className="ml-auto shrink-0 tabular-nums">
          {messages.counter(value.length, max)}
        </p>
      </div>
      {error ? (
        <p id={errorId} className="text-xs text-danger-fg">
          {error}
        </p>
      ) : null}
      <p role="status" aria-live="polite" className="text-xs text-fg-secondary empty:hidden">
        {note}
      </p>
    </div>
  )
}

export { ChipInput, type ChipInputMessages, type ChipInputProps, type ChipInputSeparator }
