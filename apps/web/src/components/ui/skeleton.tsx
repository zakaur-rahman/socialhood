import { cn } from "@/lib/utils"

/**
 * A placeholder shaped like the content (DESIGN_SYSTEM §8.2, §8.3). `raised`, so it shows on
 * every surface it sits on (`muted` was the field colour, invisible on panel); the pulse stops
 * under reduced motion (§7.4).
 */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("rounded-md bg-raised motion-safe:animate-pulse", className)}
      {...props}
    />
  )
}

export { Skeleton }
