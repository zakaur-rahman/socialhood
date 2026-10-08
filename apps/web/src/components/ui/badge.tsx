import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { TONE_CLASS } from "@/lib/ui/tone"
import { Slot } from "radix-ui"

/**
 * Status and count badges (DESIGN_SYSTEM §8.2, §2.1, §3, §4):
 *
 * - `tone`: the status tones from lib/ui/tone (`neutral`, `brand` for info, `success`, `warning`,
 *   `danger`), or `count`: the brand gradient with `on-brand` text and tabular figures, for unread
 *   and needs-reply counts (UX-SH-01);
 * - `size`: `sm` 11 px (status and signal chips), `md` 12 px (counts, and 12 px status chips),
 *   both 20 px tall; a count is at least as wide as it is tall;
 * - `shape`: `pill` (round), or `tag` (4 px corners) for thumbnail labels and counters.
 *
 * A badge isn't a control: no hover, no transition. Colour is never its only cue; it carries text.
 */
const badgeVariants = cva(
  "inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden px-2 font-medium whitespace-nowrap [&>svg]:pointer-events-none [&>svg]:size-3 [&>svg]:shrink-0",
  {
    variants: {
      tone: {
        ...TONE_CLASS,
        count: "bg-brand-gradient text-on-brand tabular-nums",
      },
      size: {
        sm: "text-2xs",
        md: "text-xs",
      },
      shape: {
        pill: "rounded-full",
        tag: "rounded-sm",
      },
    },
    // A one-digit count is a circle (AppSidebar's `h-5 min-w-5 px-1.5`).
    compoundVariants: [{ tone: "count", class: "min-w-5 px-1.5" }],
    defaultVariants: {
      tone: "neutral",
      size: "sm",
      shape: "pill",
    },
  }
)

type BadgeProps = React.ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { asChild?: boolean }

function Badge({ className, tone = "neutral", size = "sm", shape = "pill", asChild = false, ...props }: BadgeProps) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-tone={tone}
      data-size={size}
      data-shape={shape}
      className={cn(badgeVariants({ tone, size, shape }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
export type { BadgeProps }
