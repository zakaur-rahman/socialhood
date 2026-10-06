import type * as React from "react"

/**
 * The floating family: Popover, DropdownMenu and Select share one surface, one motion and one item
 * highlight, so a menu, a select and a popover float, move and highlight alike (DESIGN_SYSTEM §6,
 * §7.2, §8.3). No runtime imports, so a page with a select doesn't pull in the menu.
 */

/**
 * The floating surface (DESIGN_SYSTEM §6, level 1): the popover surface with a 1 px `line` edge and
 * the spec's `shadow-xl`, set here so call sites don't add their own. D-12 (UI-018) moves it to the
 * `overlay` surface and `shadow-floating`.
 */
export const FLOATING_SURFACE = "rounded-lg bg-popover text-popover-foreground shadow-xl ring-1 ring-foreground/10"

/**
 * The floating motion (DESIGN_SYSTEM §7.2): in and out in `duration-fast` (120 ms), with
 * `ease-enter` in and `ease-exit` out; a fade, a 97% zoom and a 4 px slide away from the trigger.
 * Under reduced motion they appear and leave at once (§7.4). `motion-reduce:` sits on the same
 * `data-open:`/`data-closed:` variant as the animation it cancels: those are custom variants, which
 * Tailwind emits after `motion-reduce:`, so a bare `motion-reduce:animate-none` loses to
 * `data-open:animate-in`.
 */
export const FLOATING_MOTION =
  "duration-fast data-open:animate-in data-open:fade-in-0 data-open:zoom-in-97 data-open:ease-enter data-open:motion-reduce:animate-none data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-97 data-closed:ease-exit data-closed:motion-reduce:animate-none data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1"

/**
 * A menu or select item (DESIGN_SYSTEM §8.3, §8.4). Radix moves focus to the highlighted item for
 * the pointer and the keyboard alike, so `focus:` is the highlight: the `hover` fill for both, and
 * for the keyboard the focus outline drawn inset (the content clips it), brand on the highlight
 * 3.96:1. Nothing removes the outline. The keyboard outline shows on `:focus-visible`, and also on
 * the highlighted item while its content is marked `data-keyboard` (see `keyboardHighlight`).
 * 40 px tall on coarse pointers; desktop density unchanged. Icons and secondary text keep their
 * colours when highlighted (secondary text is 5.2:1 on the fill).
 */
export const FLOATING_ITEM =
  "relative flex cursor-default items-center gap-1.5 rounded-md py-1 text-sm select-none pointer-coarse:min-h-10 focus:bg-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring group-data-keyboard/floating:data-highlighted:outline-2 group-data-keyboard/floating:data-highlighted:-outline-offset-2 group-data-keyboard/floating:data-highlighted:outline-ring data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"

/** The class that names a menu's or select's content as the items' group. */
export const FLOATING_GROUP = "group/floating"

type KeyboardHighlightProps = {
  onKeyDownCapture?: React.KeyboardEventHandler<HTMLDivElement>
  onPointerMove?: React.PointerEventHandler<HTMLDivElement>
}

/**
 * Marks a menu's or select's content `data-keyboard` from a key press inside it until the pointer
 * moves, so FLOATING_ITEM outlines the highlighted item for the keyboard. Firefox doesn't match
 * `:focus-visible` when arrow keys move the highlight in a menu opened with the pointer (the item
 * is focused by script after a pointer focus); Chromium does. Spread after the call site's props:
 * it calls their handlers too.
 */
export function keyboardHighlight({ onKeyDownCapture, onPointerMove }: KeyboardHighlightProps) {
  return {
    onKeyDownCapture: (event: React.KeyboardEvent<HTMLDivElement>) => {
      event.currentTarget.setAttribute("data-keyboard", "")
      onKeyDownCapture?.(event)
    },
    onPointerMove: (event: React.PointerEvent<HTMLDivElement>) => {
      event.currentTarget.removeAttribute("data-keyboard")
      onPointerMove?.(event)
    },
  }
}
