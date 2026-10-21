"use client"

import * as React from "react"

import { clampWidth } from "@/lib/use-pane-width"
import { cn } from "@/lib/utils"

const STEP = 16
const BIG_STEP = 64

type ResizeHandleProps = {
  /** The pane's current width in px. */
  value: number
  min: number
  max: number
  onChange: (width: number) => void
  /** Double-click: back to the pane's default width. */
  onReset: () => void
  /** What is being resized, for screen readers ("Resize the conversation list"). */
  label: string
  /**
   * Which edge of the pane the handle sits on. `end`: the pane's right edge (a left-hand list;
   * dragging right widens it). `start`: its left edge (a right-hand panel; dragging left widens it).
   */
  edge: "start" | "end"
  className?: string
}

/**
 * A vertical splitter for a resizable pane (UI-078): drag it, or focus it and use ← and → (16 px,
 * 64 px with Shift), Home and End for the limits; a double-click resets the width. It is a
 * `separator` with its value range, so assistive technology announces the width. Place it inside
 * the pane, which must be `relative`. Hidden below `md`: phones keep their single-pane layouts.
 */
function ResizeHandle({ value, min, max, onChange, onReset, label, edge, className }: ResizeHandleProps) {
  const [dragging, setDragging] = React.useState(false)
  const start = React.useRef({ x: 0, width: value })

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    start.current = { x: event.clientX, width: value }
    setDragging(true)
  }
  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return
    const delta = event.clientX - start.current.x
    onChange(clampWidth(start.current.width + (edge === "end" ? delta : -delta), { min, max }))
  }
  const stop = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    setDragging(false)
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? BIG_STEP : STEP
    // → widens a pane whose handle is on its right edge, ← one whose handle is on its left edge.
    const grow = edge === "end" ? "ArrowRight" : "ArrowLeft"
    const shrink = edge === "end" ? "ArrowLeft" : "ArrowRight"
    let next: number | null = null
    if (event.key === grow) next = value + step
    else if (event.key === shrink) next = value - step
    else if (event.key === "Home") next = min
    else if (event.key === "End") next = max
    if (next === null) return
    event.preventDefault()
    onChange(clampWidth(next, { min, max }))
  }

  // While dragging, the whole page shows the resize cursor and text is not selected.
  React.useEffect(() => {
    if (!dragging) return
    const { cursor, userSelect } = document.body.style
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    return () => {
      document.body.style.cursor = cursor
      document.body.style.userSelect = userSelect
    }
  }, [dragging])

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      data-slot="resize-handle"
      data-dragging={dragging || undefined}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={stop}
      onPointerCancel={stop}
      onKeyDown={onKeyDown}
      onDoubleClick={onReset}
      className={cn(
        // An 8 px hit area (16 px on touch-capable screens) centred on the pane's edge, showing a
        // 2 px brand line on hover, focus and while dragging.
        "group/resize absolute inset-y-0 z-10 hidden w-2 cursor-col-resize touch-none md:block pointer-coarse:w-4",
        edge === "end" ? "right-0 translate-x-1/2" : "left-0 -translate-x-1/2",
        "focus-visible:outline-offset-0",
        className
      )}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-transparent transition-colors duration-fast ease-standard group-hover/resize:bg-brand group-focus-visible/resize:bg-brand group-data-[dragging]/resize:bg-brand"
      />
    </div>
  )
}

export { ResizeHandle }
