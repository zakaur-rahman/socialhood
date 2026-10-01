"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Dialog as DialogPrimitive } from "radix-ui"

import { Button } from "@/components/ui/button"
import { XIcon } from "lucide-react"

/**
 * The modal family's motion (DESIGN_SYSTEM §7.2): Dialog, AlertDialog and Sheet enter in
 * `duration-slow` with `ease-enter` and leave in `duration-fast` with `ease-exit`; the scrim fades
 * over the same time as its panel. Under reduced motion they appear and leave at once (§7.4).
 * `motion-reduce:` sits on the same `data-open:`/`data-closed:` variant as the animation it cancels:
 * those are custom variants, which Tailwind emits after `motion-reduce:`, so a bare
 * `motion-reduce:animate-none` loses to `data-open:animate-in`.
 */
export const MODAL_MOTION =
  "data-open:animate-in data-open:fade-in-0 data-open:duration-slow data-open:ease-enter data-open:motion-reduce:animate-none data-closed:animate-out data-closed:fade-out-0 data-closed:duration-fast data-closed:ease-exit data-closed:motion-reduce:animate-none"

/** The modal scrim (UX-SH-02): black 60%, no blur (DESIGN_SYSTEM §6). */
export const MODAL_OVERLAY = cn("fixed inset-0 isolate z-50 bg-scrim", MODAL_MOTION)

/** Today's four dialog widths, from 640 px; below that a dialog is the viewport less 1 rem a side. */
const DIALOG_SIZES = {
  sm: "sm:max-w-sm",
  md: "sm:max-w-md",
  lg: "sm:max-w-lg",
  xl: "sm:max-w-3xl",
} as const

function Dialog({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(MODAL_OVERLAY, className)}
      {...props}
    />
  )
}

/**
 * A centred dialog. It scrolls within the viewport less 2 rem, so its actions stay reachable on
 * short screens; `size` picks the width (and `lg`/`xl` dialogs get the larger title).
 */
function DialogContent({
  className,
  children,
  size = "sm",
  showCloseButton = true,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  size?: keyof typeof DIALOG_SIZES
  showCloseButton?: boolean
}) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        data-size={size}
        className={cn(
          "group/dialog-content fixed top-1/2 left-1/2 z-50 grid max-h-[calc(100dvh-2rem)] w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 gap-4 overflow-y-auto rounded-xl bg-popover p-4 text-sm text-popover-foreground shadow-xl ring-1 ring-foreground/10 outline-none data-open:zoom-in-95 data-closed:zoom-out-95",
          MODAL_MOTION,
          DIALOG_SIZES[size],
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close data-slot="dialog-close" asChild>
            <Button
              variant="ghost"
              className="absolute top-2 right-2 pointer-coarse:size-10"
              size="icon-sm"
            >
              <XIcon
              />
              <span className="sr-only">Close</span>
            </Button>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "-mx-4 -mb-4 flex flex-col-reverse gap-2 rounded-b-xl border-t bg-muted/50 p-4 sm:flex-row sm:justify-end",
        className
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close asChild>
          <Button variant="outline">Close</Button>
        </DialogPrimitive.Close>
      )}
    </div>
  )
}

/**
 * The card-title role (16 px semibold; 18 px in `lg` and `xl` dialogs) with normal leading, so a
 * title that wraps keeps its line height. It leaves room for the close button beside it.
 */
function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn(
        "text-base font-semibold group-data-[size=lg]/dialog-content:text-lg group-data-[size=xl]/dialog-content:text-lg group-has-data-[slot=dialog-close]/dialog-content:pe-6 pointer-coarse:group-has-data-[slot=dialog-close]/dialog-content:pe-10",
        className
      )}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn(
        "text-sm text-muted-foreground *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
