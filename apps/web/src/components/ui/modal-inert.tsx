"use client"

import * as React from "react"

/**
 * Makes the page behind an open modal `inert` while it is open. Radix hides the rest of the page
 * with `aria-hidden`, which leaves its buttons and links focusable for a screen reader's own
 * navigation (axe `aria-hidden-focus`: "needs review" for every focusable node behind the modal).
 * `inert` removes them from the tab order, the pointer and the accessibility tree.
 *
 * Render it inside a modal's content. It marks only the body children it set itself, skips live
 * regions (the toaster must keep announcing) and restores them on close, before Radix returns focus.
 */
export function ModalInert() {
  const ref = React.useRef<HTMLSpanElement>(null)
  React.useEffect(() => {
    const own = ref.current?.closest("body > *")
    if (!own) return
    const marked: Element[] = []
    const mark = (el: Element) => {
      // Radix's focus guards stay focusable: they are how the modal keeps focus inside.
      if (el === own || el.tagName === "SCRIPT" || el.hasAttribute("inert") || el.matches("[aria-live], [data-radix-focus-guard]")) return
      el.setAttribute("inert", "")
      marked.push(el)
    }
    for (const el of Array.from(document.body.children)) mark(el)
    // Portals opened while the modal is up (a tooltip behind it, say) are marked too.
    const observer = new MutationObserver((records) => {
      for (const record of records) for (const node of Array.from(record.addedNodes)) if (node instanceof Element) mark(node)
    })
    observer.observe(document.body, { childList: true })
    return () => {
      observer.disconnect()
      for (const el of marked) el.removeAttribute("inert")
    }
  }, [])
  return <span ref={ref} hidden data-slot="modal-inert" />
}
