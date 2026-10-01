"use client"

import * as React from "react"
import { CheckIcon, MinusIcon } from "lucide-react"
import { Checkbox as CheckboxPrimitive } from "radix-ui"

import { useFieldControl } from "@/components/ui/field"
import { cn } from "@/lib/utils"

/**
 * DESIGN_SYSTEM §8.2: checked and indeterminate are filled with `--primary` (brand-strong) and an
 * on-brand glyph; indeterminate draws a minus and reads as "mixed" (Radix sets aria-checked).
 * Unchecked, the box is its `--input` edge (UI-018 moves the edge to line-control under D-01).
 * Focus is the global outline. The box is 16 px; its hit area is 40 × 32 px, and 40 × 40 on coarse
 * pointers (§8.4).
 */
function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  const fieldProps = useFieldControl(props)
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer group/checkbox relative flex size-4 shrink-0 items-center justify-center rounded-sm border border-input transition-[background-color,border-color] duration-fast ease-standard after:absolute after:-inset-x-3 after:-inset-y-2 pointer-coarse:after:-inset-3 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:data-unchecked:border-danger data-checked:border-primary data-checked:bg-primary data-checked:text-primary-foreground data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary data-[state=indeterminate]:text-primary-foreground",
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
