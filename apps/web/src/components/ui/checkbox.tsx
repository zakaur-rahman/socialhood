"use client"

import * as React from "react"
import { CheckIcon, MinusIcon } from "lucide-react"
import { Checkbox as CheckboxPrimitive } from "radix-ui"

import { useFieldControl } from "@/components/ui/field"
import { cn } from "@/lib/utils"

/**
 * DESIGN_SYSTEM §8.2: checked and indeterminate are filled with `brand`, like the switch's on
 * track, with an on-brand glyph; indeterminate draws a minus and reads as "mixed" (Radix sets
 * aria-checked). A checked box's edge is its fill, so the fill is the non-text `brand`: 3:1 or more
 * on every surface, `raised` (a selected row) 3.47:1 and `raised-hover` 3.01:1, where
 * `brand-strong` falls to 2.49:1 on `raised`; the tick is a graphic, 4.17:1 on it (C-071, C-128).
 * Unchecked, the box is its `line-control` edge (D-01): 3.16:1 or more. Focus is the
 * global outline. The box is 16 px; its hit area is 40 × 32 px, and 40 × 40 on coarse pointers
 * (§8.4).
 */
function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  const fieldProps = useFieldControl(props)
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer group/checkbox relative flex size-4 shrink-0 items-center justify-center rounded-sm border border-line-control transition-[background-color,border-color] duration-fast ease-standard after:absolute after:-inset-x-3 after:-inset-y-2 pointer-coarse:after:-inset-3 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:data-unchecked:border-danger data-checked:border-brand data-checked:bg-brand data-checked:text-on-brand data-[state=indeterminate]:border-brand data-[state=indeterminate]:bg-brand data-[state=indeterminate]:text-on-brand",
        className
      )}
      {...props}
      {...fieldProps}
    >
      <CheckboxPrimitive.Indicator data-slot="checkbox-indicator" className="grid place-content-center text-current [&>svg]:size-3.5">
        <CheckIcon aria-hidden className="group-data-[state=indeterminate]/checkbox:hidden" />
        <MinusIcon aria-hidden className="hidden group-data-[state=indeterminate]/checkbox:block" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
