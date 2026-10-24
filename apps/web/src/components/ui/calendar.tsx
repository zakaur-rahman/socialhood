"use client"

import * as React from "react"
import { DayPicker, type DayButton } from "react-day-picker"
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { formatDay } from "@/lib/day"
import { cn } from "@/lib/utils"

/**
 * shadcn's Calendar on react-day-picker v9, drawn with the theme's tokens only: react-day-picker's
 * own stylesheet is not imported, so every part is styled here. Arrow keys, Home/End, PageUp/Down
 * and Enter come from the library. The selected day is the brand fill, today a brand-coloured
 * number, days outside the month are dimmed (or hidden), and a range runs on `brand-soft`. Cells
 * are 36 px, 40 px on coarse pointers (the control ladder).
 */
function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  components,
  ...props
}: React.ComponentProps<typeof DayPicker>) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("w-fit p-1 text-sm", className)}
      classNames={{
        root: "w-fit",
        months: "relative flex flex-col gap-4 sm:flex-row",
        month: "flex w-full flex-col gap-2",
        nav: "absolute inset-x-0 top-0 flex items-center justify-between",
        button_previous: cn(buttonVariants({ variant: "ghost", size: "icon" }), "aria-disabled:opacity-50"),
        button_next: cn(buttonVariants({ variant: "ghost", size: "icon" }), "aria-disabled:opacity-50"),
        month_caption: "flex h-8 items-center justify-center px-9 pointer-coarse:h-10",
        caption_label: "text-sm font-medium",
        month_grid: "w-full border-collapse",
        weekdays: "flex",
        weekday: "flex size-9 items-center justify-center text-xs font-normal text-fg-secondary pointer-coarse:size-10",
        week: "mt-1 flex w-full",
        day: "relative size-9 p-0 text-center text-sm select-none pointer-coarse:size-10",
        range_start: "rounded-l-md bg-brand-soft",
        range_middle: "bg-brand-soft",
        range_end: "rounded-r-md bg-brand-soft",
        hidden: "invisible",
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation, className: chevron, ...rest }) =>
          orientation === "left" ? (
            <ChevronLeftIcon className={cn("size-4", chevron)} {...rest} />
          ) : (
            <ChevronRightIcon className={cn("size-4", chevron)} {...rest} />
          ),
        DayButton: CalendarDayButton,
        ...components,
      }}
      {...props}
    />
  )
}

/**
 * A day: the library hands over its modifiers, and the classes pick the state here so they merge
 * (a range's middle is soft, its ends and a single choice are the brand fill). The library asks for
 * focus through `modifiers.focused`, which a custom button has to honour.
 */
function CalendarDayButton({ className, day, modifiers, ...props }: React.ComponentProps<typeof DayButton>) {
  const ref = React.useRef<HTMLButtonElement>(null)
  React.useEffect(() => {
    if (modifiers.focused) ref.current?.focus()
  }, [modifiers.focused])

  const middle = modifiers.range_middle
  const chosen = modifiers.selected && !middle
  return (
    <button
      ref={ref}
      type="button"
      data-day={formatDay(day.date)}
      data-selected={chosen ? "true" : undefined}
      className={cn(
        "flex size-full items-center justify-center rounded-md text-sm font-normal tabular-nums transition-colors duration-fast hover:bg-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
        modifiers.today && "font-semibold text-brand-fg",
        modifiers.outside && "text-fg-secondary opacity-60",
        modifiers.disabled && "pointer-events-none text-fg-disabled line-through opacity-60",
        middle && "rounded-none hover:bg-brand-soft-hover",
        chosen && "bg-brand-strong font-medium text-on-brand hover:bg-brand-strong",
        className
      )}
      {...props}
    />
  )
}

export { Calendar, CalendarDayButton }
