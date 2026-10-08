"use client"

import * as React from "react"
import { SearchIcon } from "lucide-react"

import { useFieldControl } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/**
 * SearchInput: the one search field (DESIGN_SYSTEM §8.2, UI-ISS-040). An Input (same recipe,
 * sizes and touch height) with `type="search"`, a leading search icon at `left-3` (text at
 * `pl-9`), and a label. Escape clears a field that has text, through the field's own `onChange`,
 * so `value`/`onChange` and react-hook-form's `register` both see the empty value; in an empty
 * field Escape is left alone (a menu or dialog around it can close).
 *
 * `className` places the field (`flex-1`, `max-w-80`); the field's look isn't restyled at call
 * sites. Name it with `label` (visually hidden), or with a FieldLabel inside a Field, which also
 * links its descriptions and errors.
 *
 *   <SearchInput label="Search automations" placeholder="Search by name or keyword"
 *     value={text} onChange={(event) => setText(event.target.value)} className="flex-1" />
 */

type SearchInputProps = Omit<React.ComponentProps<typeof Input>, "type"> & {
  /** The field's name, visually hidden ("Search conversations"). Inside a Field, FieldLabel names it. */
  label?: string
}

/** Empties the field the way typing does, so React's onChange (controlled or not) sees "". */
function clearField(input: HTMLInputElement) {
  const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
  setValue?.call(input, "")
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

function SearchInput({ className, label, id, onKeyDown, autoComplete = "off", ...props }: SearchInputProps) {
  const generatedId = React.useId()
  const inputId = useFieldControl({ id }).id ?? id ?? generatedId

  return (
    <div data-slot="search-input" className={cn("relative min-w-0", className)}>
      <SearchIcon
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-secondary"
      />
      {label ? (
        <label htmlFor={inputId} className="sr-only">
          {label}
        </label>
      ) : null}
      <Input
        {...props}
        id={inputId}
        type="search"
        autoComplete={autoComplete}
        className="pl-9"
        onKeyDown={(event) => {
          onKeyDown?.(event)
          if (event.defaultPrevented || event.key !== "Escape" || event.currentTarget.value === "") return
          event.preventDefault()
          event.stopPropagation()
          clearField(event.currentTarget)
        }}
      />
    </div>
  )
}

export { SearchInput }
