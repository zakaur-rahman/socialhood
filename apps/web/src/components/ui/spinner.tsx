import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { LoaderCircle } from "lucide-react"

import { cn } from "@/lib/utils"

const spinnerVariants = cva("shrink-0 motion-safe:animate-spin", {
  variants: {
    size: {
      xs: "size-3",
      sm: "size-3.5",
      default: "size-4",
      lg: "size-5",
    },
  },
  defaultVariants: {
    size: "default",
  },
})

/**
 * The one loading indicator (DESIGN_SYSTEM §7.4, §8.2). It spins only when motion is allowed:
 * under reduced motion it is a static icon, and the `aria-busy` state and the label around it still
 * say "loading". Decorative by default (a Button's `loading` sets `aria-busy`); a spinner that is
 * the only sign of loading gets `role="status"` and an `aria-label` from its caller.
 */
function Spinner({
  className,
  size = "default",
  ...props
}: Omit<React.ComponentProps<typeof LoaderCircle>, "size"> & VariantProps<typeof spinnerVariants>) {
  const labelled = props["aria-label"] !== undefined || props["aria-labelledby"] !== undefined
  return (
    <LoaderCircle
      data-slot="spinner"
      aria-hidden={labelled ? undefined : true}
      className={cn(spinnerVariants({ size }), className)}
      {...props}
    />
  )
}

export { Spinner, spinnerVariants }
