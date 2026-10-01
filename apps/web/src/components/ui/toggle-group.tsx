"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui"

/**
 * The segment look, shared by ToggleGroupItem and TabsTrigger, so the two read as one control
 * (DESIGN_SYSTEM §8.2–§8.4):
 *
 * - the chosen segment is `bg-raised` with `brand-fg` text (no shadow: it does nothing on dark);
 * - focus is the global outline, drawn inset because the track clips (§8.3);
 * - labels stay on one line ("30 days", "Action needed");
 * - heights follow the control ladder on fine pointers (`sm` 28, `default` 32) and are at least
 *   40 px on coarse pointers, whatever the viewport width;
 * - a disabled segment takes no pointer events, like Button: hover, click and tap fall through to
 *   a DisabledReason wrapper around it, which says why (a disabled button swallows the click).
 */
const segmentVariants = cva(
  "inline-flex flex-1 items-center justify-center gap-1.5 rounded-md px-2.5 font-medium whitespace-nowrap text-fg-secondary transition-[color,background-color] duration-fast ease-standard hover:text-fg focus-visible:-outline-offset-2 disabled:pointer-events-none disabled:opacity-50 pointer-coarse:min-h-10",
  {
    variants: {
      size: {
        default: "min-h-8 py-1.5 text-sm",
        sm: "min-h-7 py-1 text-xs",
      },
    },
    defaultVariants: { size: "default" },
  }
)

/** The track behind the segments (UX-INB-03): `field`, inset by 4 px. */
const segmentTrackClass = "gap-1 rounded-lg bg-field p-1"

type SegmentSize = NonNullable<VariantProps<typeof segmentVariants>["size"]>
type ToggleGroupVariant = "segmented" | "chips"

/**
 * Filter chips (DESIGN_SYSTEM §8.2, D4): pills of small-control text, 28 px (40 px on coarse
 * pointers), selected `brand-soft` with `brand-fg` text and a `brand-line` edge. They ignore `size`.
 */
const chipClass =
  "inline-flex h-7 shrink-0 items-center justify-center gap-1 rounded-full border border-line px-3 text-xs font-medium whitespace-nowrap text-fg-secondary transition-[color,background-color,border-color] duration-fast ease-standard hover:bg-hover hover:text-fg focus-visible:-outline-offset-2 disabled:pointer-events-none disabled:opacity-50 pointer-coarse:min-h-10 data-[state=on]:border-brand-line data-[state=on]:bg-brand-soft data-[state=on]:text-brand-fg"

const ToggleGroupContext = React.createContext<{ variant: ToggleGroupVariant; size: SegmentSize }>({
  variant: "segmented",
  size: "default",
})

type ToggleGroupBaseProps = Omit<
  React.ComponentProps<typeof ToggleGroupPrimitive.Root>,
  "type" | "value" | "defaultValue" | "onValueChange"
> & {
  /** `segmented` (default): a track of segments. `chips`: a row of filter chips that wraps. */
  variant?: ToggleGroupVariant
  /** Segments only: `sm` is 28 px with 12 px text, for dense headers. */
  size?: SegmentSize
}

type ToggleGroupProps =
  | (ToggleGroupBaseProps & {
      /** One value; clicking the chosen item keeps it (a single group is never empty). */
      type?: "single"
      value: string
      onValueChange: (value: string) => void
    })
  | (ToggleGroupBaseProps & {
      /** Any number of values, none included. */
      type: "multiple"
      value: string[]
      onValueChange: (value: string[]) => void
    })

/**
 * Segmented control and filter chips (UX-CMP-01, UX-INB-03; DESIGN_SYSTEM §8.2). Radix gives a
 * single group `radiogroup` with `radio` items (`aria-checked`) and a multiple group `toolbar`
 * with toggle buttons (`aria-pressed`); arrow keys move between items.
 */
function ToggleGroup({ className, variant = "segmented", size = "default", ...props }: ToggleGroupProps) {
  const shared = {
    "data-slot": "toggle-group",
    "data-variant": variant,
    "data-size": size,
    className: cn(
      variant === "chips" ? "flex flex-wrap items-center gap-1.5" : cn("inline-flex w-full", segmentTrackClass),
      className
    ),
  }
  return (
    <ToggleGroupContext.Provider value={{ variant, size }}>
      {props.type === "multiple" ? (
        <ToggleGroupPrimitive.Root {...shared} {...props} />
      ) : (
        <ToggleGroupPrimitive.Root
          {...shared}
          {...props}
          type="single"
          onValueChange={(next: string) => {
            if (next) props.onValueChange(next)
          }}
        />
      )}
    </ToggleGroupContext.Provider>
  )
}

function ToggleGroupItem({ className, ...props }: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  const { variant, size } = React.useContext(ToggleGroupContext)
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(
        variant === "chips"
          ? chipClass
          : cn(segmentVariants({ size }), "data-[state=on]:bg-raised data-[state=on]:text-brand-fg"),
        className
      )}
      {...props}
    />
  )
}

export { ToggleGroup, ToggleGroupItem, segmentTrackClass, segmentVariants }
