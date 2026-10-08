"use client"

import { CircleCheck, Info, OctagonX, TriangleAlert } from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

import { buttonVariants } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { minWidth } from "@/lib/breakpoints"
import { useMediaQuery } from "@/lib/use-browser-state"

/**
 * How long a toast with an action stays: 10 s (DESIGN_SYSTEM §8.2, §10.12; WCAG 2.2.1), so a
 * keyboard or screen-reader user can reach Undo, Try again or Open before it goes. Sonner's default
 * is 4 s. Every toast with an `action` passes `duration: TOAST_ACTION_DURATION`; eslint asks for a
 * duration (eslint.config.mjs).
 */
export const TOAST_ACTION_DURATION = 10_000

/*
 * Sonner injects its stylesheet unlayered, so it beats every Tailwind utility (`@layer utilities`)
 * on the same element. The toasts are `unstyled`: these classes draw them, and sonner keeps only
 * its position, stacking and swipe rules. Three of those rules still reach every toast and need
 * `!` to lose: the transition (here on the motion tokens), `outline: 0` (the focus outline) and its
 * faint focus shadow.
 */
const TOAST = [
  // The width sonner gives the stack: 356 px, or the full width less 16 px a side below 600 px.
  "flex w-(--width) items-center gap-3 p-4 font-sans text-sm",
  // The floating surface (DESIGN_SYSTEM §6, level 1; D-12): `bg-popover`, which is `overlay`, and
  // `shadow-floating`, like ui/floating, with a `line-strong` edge, because a toast lands on any
  // surface, panels included. Errors read in `danger-fg`, icon and text.
  "rounded-lg border border-line-strong bg-popover text-fg shadow-floating data-[type=error]:text-danger-fg",
  // The toast is focusable (Alt+T, then Tab): the global focus outline, kept over sonner's `outline: 0`,
  // and its own shadow kept over sonner's focus shadow.
  "focus-visible:outline-2! focus-visible:outline-offset-2! focus-visible:outline-ring! focus-visible:shadow-floating!",
  // Motion (§7.2): in at `duration-slow` with `ease-enter`, out at `duration-fast` with `ease-exit`
  // (sonner unmounts 200 ms after the exit starts); nothing moves under reduced motion (§7.4).
  "duration-slow! ease-enter! data-[removed=true]:duration-fast! data-[removed=true]:ease-exit! motion-reduce:transition-none!",
  // Behind the front toast, a collapsed stack shows only the toasts' edges; their content fades
  // (sonner does this for its styled toasts only).
  "data-[expanded=false]:data-[front=false]:*:opacity-0 *:duration-fast! *:ease-standard! motion-reduce:*:transition-none!",
].join(" ")

/**
 * The one Toaster (DESIGN_SYSTEM §8.2), mounted once in the root layout. Top centre below `md`,
 * where a toast at the bottom would cover Send and the sticky action bars (UX-SH-04); bottom right
 * from `md`. Toasts are polite (sonner's live region). Failed requests go through `toastError`
 * (lib/toast-error), so a plan limit (402) shows only the upgrade dialog; toasts with an action last
 * `TOAST_ACTION_DURATION`.
 */
function Toaster(props: ToasterProps) {
  // No toast exists before hydration (sonner renders them on a call), so the server value only
  // names the first, empty render: phone-first.
  const desktop = useMediaQuery(minWidth("md"), false)
  return (
    <Sonner
      // No `theme`: sonner's dark theme colours the description and close button with its own
      // greys even on unstyled toasts. Every colour comes from the classes below.
      position={desktop ? "bottom-right" : "top-center"}
      icons={{
        success: <CircleCheck className="size-4" />,
        info: <Info className="size-4" />,
        warning: <TriangleAlert className="size-4" />,
        error: <OctagonX className="size-4" />,
        loading: <Spinner />,
      }}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast: TOAST,
          icon: "relative flex size-4 shrink-0 items-center justify-center",
          content: "flex min-w-0 flex-1 flex-col gap-0.5",
          title: "font-medium",
          description: "text-fg-secondary",
          // The Button recipe: 28 px on fine pointers, 40 px on coarse ones (§8.4).
          actionButton: buttonVariants({ variant: "secondary", size: "sm" }),
          cancelButton: buttonVariants({ variant: "ghost", size: "sm" }),
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
