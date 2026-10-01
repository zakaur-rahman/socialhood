"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui"

/**
 * Segmented control (UX-CMP-01, UX-INB-03 styling): bg-field track, the chosen segment in
 * bg-raised with brand text. Single choice only; clicking the chosen segment keeps it.
 */
function ToggleGroup({
  className,
  onValueChange,
  ...props
}: Omit<React.ComponentProps<typeof ToggleGroupPrimitive.Root>, "type" | "onValueChange" | "value" | "defaultValue"> & {
  value: string
  onValueChange: (value: string) => void
}) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      type="single"
      onValueChange={(value: string) => {
        if (value) onValueChange(value)
      }}
      className={cn("inline-flex w-full gap-1 rounded-lg bg-field p-1", className)}
      {...props}
    />
  )
}

function ToggleGroupItem({ className, ...props }: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(
        "inline-flex min-h-8 flex-1 items-center justify-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-fg-secondary outline-none hover:text-fg focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-raised data-[state=on]:text-brand-fg data-[state=on]:shadow-sm",
        className
      )}
      {...props}
    />
  )
}

export { ToggleGroup, ToggleGroupItem }
