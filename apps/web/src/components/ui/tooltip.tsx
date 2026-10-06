"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Tooltip as TooltipPrimitive } from "radix-ui"

function TooltipProvider({
  delayDuration = 0,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      data-slot="tooltip-provider"
      delayDuration={delayDuration}
      {...props}
    />
  )
}

function Tooltip({
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Root>) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />
}

function TooltipTrigger({
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Trigger>) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" {...props} />
}

/**
 * The tooltip's surface (DESIGN_SYSTEM §6, level 1; owner decision D-03, C-069): dark, like every
 * other floating surface, not shadcn's inverted white bubble. `overlay` with `fg` text (15.1:1), the
 * floating family's 1 px `line` edge drawn as a ring and its `shadow-floating` (`ui/floating`), on
 * the tooltip's `rounded-md`.
 */
const TOOLTIP_SURFACE = "rounded-md bg-overlay text-fg ring-1 ring-line shadow-floating"

/**
 * The tooltip's motion (DESIGN_SYSTEM §7.2): after the provider's delay it fades in over
 * `duration-fast` (120 ms) with `ease-enter`, rising 4 px from its trigger, and fades out with
 * `ease-exit`. An `instant-open` (moving between triggers within the skip delay) has no entrance.
 * Under reduced motion it appears and leaves at once (§7.4): `motion-reduce:` sits on the same
 * state variant as the animation it cancels, which Tailwind emits after a bare `motion-reduce:`.
 */
const TOOLTIP_MOTION =
  "duration-fast data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 data-[state=delayed-open]:ease-enter data-[state=delayed-open]:motion-reduce:animate-none data-closed:animate-out data-closed:fade-out-0 data-closed:ease-exit data-closed:motion-reduce:animate-none data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1"

/**
 * The arrow matches the surface: an `overlay` square turned 45° and centred on the content's edge,
 * so its inner half merges into the content and covers the edge ring where they meet, and its two
 * outer sides carry the same `line` edge. Radix turns the arrow to face the trigger, so these are
 * always the right and bottom sides. `bg-clip-padding` draws that edge over the page, like the ring.
 */
const TOOLTIP_ARROW =
  "z-50 size-2.5 -translate-y-1/2 rotate-45 border-r border-b border-line bg-overlay bg-clip-padding fill-overlay"

function TooltipContent({
  className,
  sideOffset = 0,
  children,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "z-50 inline-flex w-fit max-w-xs origin-(--radix-tooltip-content-transform-origin) items-center gap-1.5 px-3 py-1.5 text-xs has-data-[slot=kbd]:pr-1.5 **:data-[slot=kbd]:relative **:data-[slot=kbd]:isolate **:data-[slot=kbd]:z-50 **:data-[slot=kbd]:rounded-sm",
          TOOLTIP_SURFACE,
          TOOLTIP_MOTION,
          className
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow data-slot="tooltip-arrow" className={TOOLTIP_ARROW} />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
}

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger }
