import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"
import { CARD_TITLE } from "@/styles/tokens"

/**
 * Card: the one card surface (DESIGN_SYSTEM §8.2; UI-ISS-036, 049, 092). Flat `panel` with a 1 px
 * `line` edge and no shadow (§6), `rounded-xl` for every app card (owner decision D-02).
 *
 * - `padding`: `standard` 16 px for data and dashboard cards, `roomy` 20 px on phones and 24 px
 *   from `md` for settings, billing, forms and plan cards (§3).
 * - `tone`: `default`; `danger`, a 2 px `danger` leading edge (the danger zone; §5's status edge);
 *   `brand`, a `brand-line` edge (§1.4's brand border; the current plan).
 * - The padding is the `--card-padding` variable, so what sits inside can line up with it:
 *   CardBleed runs a table, a divider or a row list to the card's edges without negative margins,
 *   and a bled table's edge cells pad with `--card-padding` to keep their text on the card's edge
 *   (§3, "Table cells").
 * - `asChild` renders the card as its child (a `section` named by its title, an `li`).
 *
 * Stack the content with `space-y-*` on the card; cards don't nest (an inner group is CardInset).
 *
 *   <Card asChild padding="roomy">
 *     <section aria-labelledby="payments-title">
 *       <CardHeader>
 *         <CardTitle id="payments-title">Payment history</CardTitle>
 *         <CardDescription>Invoices from Dodo Payments.</CardDescription>
 *         <CardAction><Button size="sm" variant="secondary">Manage billing</Button></CardAction>
 *       </CardHeader>
 *       <CardBleed>…a table…</CardBleed>
 *     </section>
 *   </Card>
 */
const cardVariants = cva("group/card min-w-0 rounded-xl border border-line bg-panel p-(--card-padding) text-fg", {
  variants: {
    padding: {
      standard: "[--card-padding:--spacing(4)]",
      roomy: "[--card-padding:--spacing(5)] md:[--card-padding:--spacing(6)]",
    },
    tone: {
      default: "",
      danger: "border-l-2 border-l-danger",
      brand: "border-brand-line",
    },
  },
  defaultVariants: { padding: "standard", tone: "default" },
})

type CardProps = React.ComponentProps<"div"> & VariantProps<typeof cardVariants> & { asChild?: boolean }

function Card({ className, padding = "standard", tone = "default", asChild = false, ...props }: CardProps) {
  const Comp = asChild ? Slot.Root : "div"
  return (
    <Comp
      data-slot="card"
      data-padding={padding}
      data-tone={tone}
      className={cn(cardVariants({ padding, tone }), className)}
      {...props}
    />
  )
}

/**
 * The title block: CardTitle, then CardDescription 4 px below it (§3), with CardAction (a button
 * or a menu) at the top right, 12 px from the text.
 */
function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "grid min-w-0 auto-rows-min items-start gap-x-3 gap-y-1 has-data-[slot=card-action]:grid-cols-[minmax(0,1fr)_auto]",
        className
      )}
      {...props}
    />
  )
}

/** The card title role (16 px semibold, §2.1). An `h2` by default; `asChild` for another level. */
function CardTitle({ className, asChild = false, ...props }: React.ComponentProps<"h2"> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "h2"
  return <Comp data-slot="card-title" className={cn(CARD_TITLE, className)} {...props} />
}

/**
 * One line under the title in `fg-secondary`: 12 px in standard cards (dashboards), 14 px in
 * roomy ones (settings and forms), from the card's own padding, so call sites don't choose (§2.2).
 */
function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-xs text-fg-secondary group-data-[padding=roomy]/card:text-sm", className)}
      {...props}
    />
  )
}

/** The header's action slot, top right beside the title and description. */
function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn("col-start-2 row-span-2 row-start-1 flex items-center gap-2 self-start justify-self-end", className)}
      {...props}
    />
  )
}

/**
 * A group inside a card: `rounded-lg` (the card's 12 px less its padding, §4) with a `line` edge
 * (§5). `standard` 16 px for form groups, `compact` 12 px for rows (§3). It sets `--card-padding`
 * to its own padding, so CardBleed inside it runs to its edges.
 */
const cardInsetVariants = cva("min-w-0 rounded-lg border border-line p-(--card-padding)", {
  variants: {
    padding: {
      standard: "[--card-padding:--spacing(4)]",
      compact: "[--card-padding:--spacing(3)]",
    },
  },
  defaultVariants: { padding: "standard" },
})

type CardInsetProps = React.ComponentProps<"div"> & VariantProps<typeof cardInsetVariants> & { asChild?: boolean }

function CardInset({ className, padding = "standard", asChild = false, ...props }: CardInsetProps) {
  const Comp = asChild ? Slot.Root : "div"
  return (
    <Comp
      data-slot="card-inset"
      data-padding={padding}
      className={cn(cardInsetVariants({ padding }), className)}
      {...props}
    />
  )
}

/**
 * Full bleed: spans the card's padding box, edge to edge, wherever it sits in the card's content
 * (not inside another padded element). It is widened by twice `--card-padding` and shifted back by
 * one, so no negative margin is needed and it always matches the card's padding at every width.
 */
function CardBleed({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-bleed"
      className={cn("relative -start-(--card-padding) w-[calc(100%+2*var(--card-padding))]", className)}
      {...props}
    />
  )
}

export { Card, CardAction, CardBleed, CardDescription, CardHeader, CardInset, CardTitle, cardVariants }
