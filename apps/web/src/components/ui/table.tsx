"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Table: the one data table (DESIGN_SYSTEM §8.2, §2.1, §3; UI-ISS-051). Three tables used three
 * header styles and three paddings; they share this one.
 *
 * - **Header:** `text-xs font-medium text-fg-secondary`, sentence case, `py-2`, one line;
 *   TableHead is `scope="col"` unless told otherwise.
 * - **Body:** `text-sm`, `py-3`, top-aligned (cells of two lines read from their first line);
 *   digits are tabular so figures line up (right-align a numeric column with `text-right`).
 * - **Rows** are divided by `line-subtle` (§5), the last one open.
 * - **Edges:** inner cells pad 12 px (`px-3`); the first and last cells pad `--card-padding`, so in
 *   a Card the table goes in CardBleed and its text lines up with the card's title. Outside a card
 *   the edge is 12 px too.
 * - **Width:** the table scrolls inside its container, never the page (320 px). For a table that
 *   may be wider than its column, `scrollLabel` makes the container a named region that takes
 *   keyboard focus while it scrolls, so it can be scrolled by keyboard (its focus outline is inset:
 *   it may sit in a clipping frame).
 * - **Caption:** TableCaption names the table (visually hidden with `sr-only` when the card's title
 *   already says what it is).
 *
 *   <CardBleed>
 *     <Table>
 *       <TableCaption className="sr-only">Payments, newest first</TableCaption>
 *       <TableHeader><TableRow><TableHead>Date</TableHead>…</TableRow></TableHeader>
 *       <TableBody><TableRow><TableCell>4 Oct 2026</TableCell>…</TableRow></TableBody>
 *     </Table>
 *   </CardBleed>
 */

/** The first and last cells pad to the card's edge (or 12 px outside a card). */
const edgeCells = "first:ps-(--table-edge) last:pe-(--table-edge)"

/** Whether the element scrolls sideways (its content is wider than it), kept current on resize. */
function useScrollsX(ref: React.RefObject<HTMLElement | null>, enabled: boolean) {
  const [scrolls, setScrolls] = React.useState(false)
  React.useEffect(() => {
    const element = ref.current
    if (!enabled || !element) return
    // A ResizeObserver reports once when it starts observing, then on every resize.
    const observer = new ResizeObserver(() => setScrolls(element.scrollWidth > element.clientWidth + 1))
    observer.observe(element)
    if (element.firstElementChild) observer.observe(element.firstElementChild)
    return () => observer.disconnect()
  }, [ref, enabled])
  return scrolls
}

function Table({
  className,
  scrollLabel,
  ...props
}: React.ComponentProps<"table"> & {
  /** Names the scrolling container, a region that takes focus while it scrolls: for tables that may not fit. */
  scrollLabel?: string
}) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const scrolls = useScrollsX(containerRef, Boolean(scrollLabel))
  return (
    <div
      ref={containerRef}
      data-slot="table-container"
      role={scrollLabel ? "region" : undefined}
      aria-label={scrollLabel}
      tabIndex={scrollLabel && scrolls ? 0 : undefined}
      className="relative w-full max-w-full overflow-x-auto [--table-edge:var(--card-padding,--spacing(3))] focus-visible:-outline-offset-2"
    >
      <table
        data-slot="table"
        className={cn("w-full caption-bottom border-collapse text-sm text-fg tabular-nums", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead data-slot="table-header" className={className} {...props} />
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props} />
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return <tr data-slot="table-row" className={cn("border-b border-line-subtle", className)} {...props} />
}

function TableHead({ className, scope = "col", ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      scope={scope}
      className={cn(
        "px-3 py-2 text-left align-middle text-xs font-medium whitespace-nowrap text-fg-secondary",
        edgeCells,
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return <td data-slot="table-cell" className={cn("px-3 py-3 align-top", edgeCells, className)} {...props} />
}

function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("px-(--table-edge) pt-3 text-left text-xs text-fg-secondary", className)}
      {...props}
    />
  )
}

export { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow }
