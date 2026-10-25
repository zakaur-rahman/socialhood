"use client"

import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { Select as SelectPrimitive } from "radix-ui"
import { ChevronDownIcon, CheckIcon, ChevronUpIcon } from "lucide-react"

import {
  FLOATING_GROUP,
  FLOATING_ITEM,
  FLOATING_MOTION,
  FLOATING_SURFACE,
  keyboardHighlight,
} from "@/components/ui/floating"
import { inputVariants } from "@/components/ui/input"

function Select({
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Root>) {
  return <SelectPrimitive.Root data-slot="select" {...props} />
}

function SelectGroup({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Group>) {
  return (
    <SelectPrimitive.Group
      data-slot="select-group"
      className={cn("scroll-my-1", className)}
      {...props}
    />
  )
}

function SelectValue({
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Value>) {
  return <SelectPrimitive.Value data-slot="select-value" {...props} />
}

/**
 * The trigger is built on Input (DESIGN_SYSTEM §8.2), so a select beside an Input on one card looks
 * the same: ui/input's `inputVariants` gives the `field` surface, the `line-control` edge, focus as the
 * global outline plus a `ring` border, `aria-invalid` in `danger`, Input's text sizes and the
 * control ladder's heights (40 px on coarse pointers at every size). On top: as wide as its value,
 * room for the chevron, and the placeholder colour. A call site's height or width class still
 * replaces the size's.
 */
const SELECT_TRIGGER =
  "flex w-fit items-center justify-between gap-1.5 pr-2 whitespace-nowrap select-none data-placeholder:text-fg-secondary *:data-[slot=select-value]:min-w-0 *:data-[slot=select-value]:line-clamp-1 *:data-[slot=select-value]:flex *:data-[slot=select-value]:items-center *:data-[slot=select-value]:gap-1.5 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"

function SelectTrigger({
  className,
  size = "default",
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger> & VariantProps<typeof inputVariants>) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      data-size={size}
      className={cn(inputVariants({ size }), SELECT_TRIGGER, className)}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDownIcon className="pointer-events-none size-4 text-fg-secondary" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  )
}

/**
 * The options, on the floating surface and motion shared with menus and popovers (ui/floating).
 * Popper by default: under the trigger, left edges aligned, at least as wide as it, 4 px off, and
 * scrolling past 24 rem. `position="item-aligned"` places the chosen option over the trigger
 * instead, and then appears without motion.
 */
function SelectContent({
  className,
  children,
  position = "popper",
  align = "start",
  sideOffset = 4,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        data-slot="select-content"
        data-align-trigger={position === "item-aligned"}
        className={cn(
          "relative z-50 max-h-[min(24rem,var(--radix-select-content-available-height))] min-w-36 origin-(--radix-select-content-transform-origin) overflow-x-hidden overflow-y-auto",
          FLOATING_GROUP,
          FLOATING_SURFACE,
          FLOATING_MOTION,
          "data-[align-trigger=true]:animate-none",
          className
        )}
        position={position}
        align={align}
        sideOffset={position === "popper" ? sideOffset : undefined}
        {...props}
        {...keyboardHighlight(props)}
      >
        <SelectScrollUpButton />
        <SelectPrimitive.Viewport
          data-position={position}
          className={cn("p-1", "data-[position=popper]:w-full data-[position=popper]:min-w-(--radix-select-trigger-width)")}
        >
          {children}
        </SelectPrimitive.Viewport>
        <SelectScrollDownButton />
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  )
}

/** A group's heading: small and muted, with an optional leading icon (a platform mark, say). */
function SelectLabel({
  className,
  icon,
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Label> & { icon?: React.ReactNode }) {
  return (
    <SelectPrimitive.Label
      data-slot="select-label"
      className={cn(
        "flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-fg-secondary [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
        className
      )}
      {...props}
    >
      {icon}
      {children}
    </SelectPrimitive.Label>
  )
}

/**
 * An option: the menu item's highlight (ui/floating). The tick sits in a fixed slot on the left, so
 * labels line up chosen or not. Only the label goes inside `ItemText`, which Radix copies into the
 * trigger; the optional `icon` and one-line `description` stay outside it, so the trigger shows the
 * label alone (or whatever `SelectValue` is given as children).
 */
function SelectItem({
  className,
  children,
  icon,
  description,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Item> & {
  icon?: React.ReactNode
  description?: React.ReactNode
}) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(FLOATING_ITEM, "w-full py-1.5 pr-2 pl-8", className)}
      // Radix names an option by its text; an `aria-label` (the full name of a shortened label) wins.
      {...(props["aria-label"] ? { "aria-labelledby": undefined } : null)}
      {...props}
    >
      <span className="pointer-events-none absolute left-2 flex size-4 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <CheckIcon className="pointer-events-none" />
        </SelectPrimitive.ItemIndicator>
      </span>
      {icon ? <span className="flex shrink-0 items-center text-fg-secondary">{icon}</span> : null}
      <span className="flex min-w-0 flex-1 flex-col">
        <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
        {description ? <span className="text-xs text-fg-secondary">{description}</span> : null}
      </span>
    </SelectPrimitive.Item>
  )
}

function SelectSeparator({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Separator>) {
  return (
    <SelectPrimitive.Separator
      data-slot="select-separator"
      className={cn("pointer-events-none -mx-1 my-1 h-px bg-line", className)}
      {...props}
    />
  )
}

function SelectScrollUpButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollUpButton>) {
  return (
    <SelectPrimitive.ScrollUpButton
      data-slot="select-scroll-up-button"
      className={cn(
        "z-10 flex cursor-default items-center justify-center bg-overlay py-1 [&_svg:not([class*='size-'])]:size-4",
        className
      )}
      {...props}
    >
      <ChevronUpIcon
      />
    </SelectPrimitive.ScrollUpButton>
  )
}

function SelectScrollDownButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollDownButton>) {
  return (
    <SelectPrimitive.ScrollDownButton
      data-slot="select-scroll-down-button"
      className={cn(
        "z-10 flex cursor-default items-center justify-center bg-overlay py-1 [&_svg:not([class*='size-'])]:size-4",
        className
      )}
      {...props}
    >
      <ChevronDownIcon
      />
    </SelectPrimitive.ScrollDownButton>
  )
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
}
