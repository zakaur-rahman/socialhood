"use client"

import * as React from "react"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

/**
 * Says why a control is disabled (DESIGN_SYSTEM §8.3, UI-ISS-026). A disabled button takes no
 * pointer events and no focus, so a `title` on it never shows and keyboard and touch users can't
 * reach it. DisabledReason wraps the control in a focusable span that shows the reason in a Tooltip
 * on hover, on keyboard focus and on tap, and describes itself with an `sr-only` copy of the reason
 * (`aria-describedby`), which screen readers also meet in reading order.
 *
 * With no `reason` the span stays (so the layout doesn't change when the control is enabled) but
 * is neither focusable nor described. Layout classes that the control would carry in its row
 * (`flex-1`, `w-full`) go on DisabledReason's `className`.
 *
 *   <DisabledReason reason={windowClosed ? "Scheduling needs an open reply window" : null}>
 *     <Button disabled={windowClosed}>Schedule</Button>
 *   </DisabledReason>
 */
function DisabledReason({
  reason,
  side = "top",
  className,
  children,
}: {
  /** Why the control is disabled; null or empty when it is enabled. */
  reason?: string | null
  side?: React.ComponentProps<typeof TooltipContent>["side"]
  className?: string
  children: React.ReactNode
}) {
  const id = React.useId()
  const [open, setOpen] = React.useState(false)
  const active = Boolean(reason)

  return (
    <Tooltip open={active && open} onOpenChange={setOpen}>
      <TooltipTrigger asChild>
        <span
          data-slot="disabled-reason"
          tabIndex={active ? 0 : undefined}
          aria-describedby={active ? id : undefined}
          className={cn("inline-flex rounded-lg", className)}
          onClick={(event) => {
            if (!active) return
            // A tap shows the reason (tooltips don't open on touch); stop the trigger's own click
            // handler from closing it again.
            event.preventDefault()
            setOpen(true)
          }}
        >
          {children}
        </span>
      </TooltipTrigger>
      {active ? (
        <span id={id} className="sr-only">
          {reason}
        </span>
      ) : null}
      <TooltipContent side={side}>{reason}</TooltipContent>
    </Tooltip>
  )
}

export { DisabledReason }
