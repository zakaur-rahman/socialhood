"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Tabs as TabsPrimitive } from "radix-ui"

import { segmentTrackClass, segmentVariants, type SegmentSize } from "@/components/ui/toggle-group"

/** The segmented control's sizes: the same segment, so a tab row and a toggle row line up. */
type TabsSize = SegmentSize

const TabsSizeContext = React.createContext<TabsSize>("default")

/** Tabs swap panels (DESIGN_SYSTEM §8.2); to choose a value without panels, use ToggleGroup. */
function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root data-slot="tabs" className={cn("flex flex-col gap-3", className)} {...props} />
}

/** The same track and segments as the segmented control (UX-INB-03), with the same `size`. */
function TabsList({
  className,
  size = "default",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> & {
  /** `sm` is 28 px with 12 px text, for dense headers; `xl` is 40 px with 14 px text, for settings forms. */
  size?: TabsSize
}) {
  return (
    <TabsSizeContext.Provider value={size}>
      <TabsPrimitive.List
        data-slot="tabs-list"
        data-size={size}
        className={cn("grid auto-cols-fr grid-flow-col", segmentTrackClass, className)}
        {...props}
      />
    </TabsSizeContext.Provider>
  )
}

function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  const size = React.useContext(TabsSizeContext)
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        segmentVariants({ size }),
        "data-[state=active]:bg-raised data-[state=active]:text-brand-fg",
        className
      )}
      {...props}
    />
  )
}

/** The panel is focusable (Radix), so it keeps the global focus outline for keyboard users. */
function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content data-slot="tabs-content" className={className} {...props} />
}

export { Tabs, TabsContent, TabsList, TabsTrigger }
