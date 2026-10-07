"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { useFieldControl } from "@/components/ui/field"
import { cn } from "@/lib/utils"

/**
 * The text-field look, shared by Input and Textarea (and by the select trigger, SearchInput and
 * ChipInput when they adopt it), so fields on one card look the same (DESIGN_SYSTEM §8.2, §8.3):
 *
 * - the `field` surface, `raised` while focused; focus is the global outline plus a `ring` border;
 *   `aria-invalid` turns the border `danger`; disabled is `opacity-50`;
 * - the edge is `--input` and the placeholder `muted-foreground` (fg-secondary), so the token
 *   decisions D-01 and D-06 (UI-018) land in globals.css and here, in one place;
 * - 16 px text below `md`, where iOS zooms into anything smaller, and 14 px from `md` (the Input
 *   type role). Written as `max-md:text-base` so a call site's leftover `text-sm` can't bring the
 *   zoom back;
 * - colour transitions only (never `outline-color`: the focus ring appears at once).
 */
const fieldControlClass =
  "w-full min-w-0 rounded-lg border border-input bg-field px-3 text-sm text-fg max-md:text-base placeholder:text-muted-foreground transition-[color,background-color,border-color] duration-fast ease-standard focus-visible:border-ring focus-visible:bg-raised disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-danger"

/** Heights on the control ladder (DESIGN_SYSTEM §8.4); 40 px on coarse pointers at every size. */
const inputVariants = cva(
  cn(
    fieldControlClass,
    "py-1 pointer-coarse:min-h-10 file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-fg"
  ),
  {
    variants: {
      size: {
        sm: "h-7",
        default: "h-8",
        lg: "h-9",
        xl: "h-10",
      },
    },
    defaultVariants: { size: "default" },
  }
)

/**
 * Native date and time fields (D-04) hold their own controls: the date or time segments and the
 * calendar or clock button. While that button has keyboard focus, Chromium leaves the field
 * matching neither `:focus` nor `:focus-visible`, only `:focus-within`, so the global outline and the
 * ring border both disappeared on that Tab stop. These types draw the same focus look from
 * `:focus-within`: the outline (2 px `ring`, offset 2 px, like the global rule), the `ring` border and
 * the `raised` fill. The browser still rings the button itself, so the stop inside the field shows.
 */
const PICKER_TYPES = new Set(["date", "time", "datetime-local", "month", "week"])

const pickerFocusClass =
  "focus-within:border-ring focus-within:bg-raised focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ring"

type InputProps = Omit<React.ComponentProps<"input">, "size"> & VariantProps<typeof inputVariants>

function Input({ className, type, size = "default", ...props }: InputProps) {
  const fieldProps = useFieldControl(props)
  return (
    <input
      type={type}
      data-slot="input"
      data-size={size}
      className={cn(inputVariants({ size }), type && PICKER_TYPES.has(type) && pickerFocusClass, className)}
      {...props}
      {...fieldProps}
    />
  )
}

export { Input, inputVariants, fieldControlClass }
