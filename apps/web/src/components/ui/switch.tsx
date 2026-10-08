"use client"

import * as React from "react"
import { Switch as SwitchPrimitive } from "radix-ui"

import { useFieldControl } from "@/components/ui/field"
import { cn } from "@/lib/utils"

/**
 * DESIGN_SYSTEM §8.2: on, the track is `brand` (a non-text mark); off, it is `pressed` inside an
 * `--input` edge. Only the edge follows `--input`: the track's fill never does, so UI-018's
 * control-edge token (D-01) can't turn it into a light slab. Focus is the global outline. The thumb
 * slides in 120 ms and jumps under reduced motion. Hit area 56 × 34 px, at least 40 px tall on
 * coarse pointers (§8.4).
 */
function Switch({
  className,
  size = "default",
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root> & {
  size?: "sm" | "default"
}) {
  const fieldProps = useFieldControl(props)
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      data-size={size}
      className={cn(
        "peer group/switch relative inline-flex shrink-0 items-center rounded-full border transition-[background-color,border-color] duration-fast ease-standard after:absolute after:-inset-x-3 after:-inset-y-2 pointer-coarse:after:-inset-y-3 data-[size=default]:h-[18.4px] data-[size=default]:w-[32px] data-[size=sm]:h-[14px] data-[size=sm]:w-[24px] pointer-coarse:data-[size=sm]:after:-inset-y-3.5 data-checked:border-transparent data-checked:bg-brand data-unchecked:border-input data-unchecked:bg-pressed aria-invalid:border-danger data-disabled:cursor-not-allowed data-disabled:opacity-50",
        className
      )}
      {...props}
      {...fieldProps}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className="pointer-events-none block rounded-full bg-fg transition-transform duration-fast ease-standard motion-reduce:transition-none data-checked:bg-on-brand group-data-[size=default]/switch:size-4 group-data-[size=sm]/switch:size-3 group-data-[size=default]/switch:data-checked:translate-x-[calc(100%-2px)] group-data-[size=sm]/switch:data-checked:translate-x-[calc(100%-2px)] group-data-[size=default]/switch:data-unchecked:translate-x-0 group-data-[size=sm]/switch:data-unchecked:translate-x-0"
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
