import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

/**
 * The one button (DESIGN_SYSTEM §8.2–§8.4). `default` is the primary: the brand gradient, one per
 * view region (D-10). Focus is the global `:focus-visible` outline (2 px brand, offset 2 px), so
 * there is no `outline-none` and no ring here. Heights follow the control ladder on fine pointers
 * (24/28/32/36/40) and are at least 40 px on coarse pointers, whatever the viewport width.
 */
const buttonRecipe = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap select-none transition-[color,background-color,border-color,filter] duration-fast ease-standard motion-reduce:transition-none active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-danger [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-brand-gradient text-on-brand hover:brightness-110 active:brightness-95",
        secondary: "bg-raised text-fg hover:bg-raised-hover aria-expanded:bg-raised-hover",
        outline:
          "border-line-strong bg-transparent hover:bg-hover hover:text-fg aria-expanded:bg-pressed aria-expanded:text-fg",
        ghost: "hover:bg-hover hover:text-fg aria-expanded:bg-pressed aria-expanded:text-fg",
        // AI actions and a pressed toggle: the AI pill's brand-soft (DESIGN_SYSTEM §1.4, the selected
        // chip's colours), brand-fg text 6.83:1, a step stronger on hover and while its menu is open.
        soft: "border-brand-line bg-brand-soft text-brand-fg hover:bg-brand-soft-hover aria-expanded:bg-brand-soft-hover",
        destructive: "bg-danger-fill text-on-brand hover:bg-danger-fill/90",
        "destructive-ghost": "text-danger-fg hover:bg-danger-soft aria-expanded:bg-danger-soft",
        link: "text-brand-fg underline-offset-4 hover:underline",
      },
      size: {
        xs: "h-6 gap-1 rounded-md px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 pointer-coarse:min-h-10 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-md px-2.5 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 pointer-coarse:min-h-10 [&_svg:not([class*='size-'])]:size-3.5",
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 pointer-coarse:min-h-10",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 pointer-coarse:min-h-10",
        xl: "h-10 gap-1.5 px-4 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        "icon-xs": "size-6 rounded-md pointer-coarse:size-10 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-7 rounded-md pointer-coarse:size-10",
        icon: "size-8 pointer-coarse:size-10",
        "icon-lg": "size-9 pointer-coarse:size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

/**
 * The button's classes for an element that isn't a Button (a toast's action, a link), merged as
 * Button merges them. cva only joins the recipe's parts, so without the merge the base's
 * `border-transparent` and `outline`'s `border-line-strong`, or `text-sm` and a small size's
 * `text-xs`, would both stay and the stylesheet's order would pick the winner (the outline edge
 * lost). A `className` among the props is merged last, so it wins.
 */
function buttonVariants(props?: Parameters<typeof buttonRecipe>[0]): string {
  return cn(buttonRecipe(props))
}

type ButtonSize = NonNullable<VariantProps<typeof buttonRecipe>["size"]>

/** The spinner matches the icon size of each button size. */
const SPINNER_SIZE: Record<ButtonSize, "xs" | "sm" | "default"> = {
  xs: "xs",
  "icon-xs": "xs",
  sm: "sm",
  default: "default",
  lg: "default",
  xl: "default",
  "icon-sm": "default",
  icon: "default",
  "icon-lg": "default",
}

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonRecipe> & {
    asChild?: boolean
    /**
     * A request is in flight: shows a Spinner over the content (which keeps the button's width),
     * sets `aria-busy` and disables the button. Ignored with `asChild`, apart from `aria-busy`.
     */
    loading?: boolean
  }) {
  // One merge: the recipe and the call site's className together.
  let classes = cn(buttonRecipe({ variant, size }), className)
  let content = children

  if (asChild) {
    // Slot appends the child's own className after ours without resolving conflicts, so an
    // override on the child (AlertDialogAction passes its className there) would lose to the
    // variant by stylesheet order. Merge it here, so `bg-danger-fill` replaces the gradient.
    if (React.isValidElement<{ className?: unknown }>(children) && typeof children.props.className === "string") {
      classes = cn(classes, children.props.className)
      content = React.cloneElement(children, { className: undefined })
    }
  } else if (loading) {
    // Both layers share one grid cell: the content keeps its size (and the accessible name) but
    // is transparent, and the spinner sits in its middle.
    content = (
      <span data-slot="button-loading" className="grid place-items-center gap-[inherit]">
        <span className="col-start-1 row-start-1 inline-flex items-center justify-center gap-[inherit] opacity-0">
          {children}
        </span>
        <Spinner className="col-start-1 row-start-1" size={SPINNER_SIZE[size ?? "default"]} />
      </span>
    )
  }

  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      data-loading={loading || undefined}
      aria-busy={loading || undefined}
      disabled={!asChild && loading ? true : disabled}
      className={classes}
      {...props}
    >
      {content}
    </Comp>
  )
}

export { Button, buttonVariants }
