import * as React from "react"
import { cva } from "class-variance-authority"
import { X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { TONE_CLASS, TONES, type Tone } from "@/lib/ui/tone"
import { cn } from "@/lib/utils"

type AlertVariant = "soft" | "outline"

/**
 * The leading edge of an `outline` alert: §5's 2 px status edge in the tone's colour (`brand` for
 * info, `line-strong` for neutral). The text carries the meaning; the edge only marks the tone.
 */
const TONE_EDGE: Record<Tone, string> = {
  neutral: "border-l-line-strong",
  brand: "border-l-brand",
  success: "border-l-success",
  warning: "border-l-warning",
  danger: "border-l-danger",
}

/** The tone's text colour, from the one tone map (`text-warning`, `text-danger-fg` …). */
function toneText(tone: Tone) {
  return TONE_CLASS[tone].split(" ").find((c) => c.startsWith("text-")) ?? ""
}

const alertVariants = cva(
  "group/alert @container/alert flex w-full min-w-0 items-start gap-2 rounded-lg px-4 py-2.5 text-sm",
  {
    variants: {
      variant: {
        soft: "",
        outline: "border border-l-2 border-line bg-panel text-fg",
      },
      tone: { neutral: "", brand: "", success: "", warning: "", danger: "" },
    },
    // `soft`: the tone's soft fill and text colour from the tone map (the pairs Badge draws), no
    // border. `outline`: `panel` with a `line` edge and the tone's leading edge.
    compoundVariants: TONES.flatMap((tone) => [
      { variant: "soft" as const, tone, class: TONE_CLASS[tone] },
      { variant: "outline" as const, tone, class: TONE_EDGE[tone] },
    ]),
    defaultVariants: { variant: "soft", tone: "neutral" },
  }
)

type AlertProps = Omit<React.ComponentProps<"div">, "role"> & {
  /** neutral, brand (the info tone), success, warning or danger (lib/ui/tone). */
  tone?: Tone
  /** `soft`: the tone's soft fill, no border. `outline`: `panel` with the tone's leading edge. */
  variant?: AlertVariant
  /**
   * A critical state the user must act on (UX-SH-04: payment on hold, an account to reconnect):
   * announced at once (`role="alert"`) and never dismissible. Danger alerts are always urgent;
   * the rest are polite (`role="status"`).
   */
  urgent?: boolean
  /** A lucide icon, 16 px, in the tone's colour; decorative (the text says what happened). */
  icon?: React.ReactNode
  /** One action: an `AlertAction` (Button `secondary`, `sm`), or a Link through its `asChild`. */
  action?: React.ReactNode
  /** Shows a Dismiss button. Ignored for urgent and danger alerts: critical states stay. */
  onDismiss?: () => void
  /** The Dismiss button's accessible name. */
  dismissLabel?: string
}

/**
 * Banners and callouts (DESIGN_SYSTEM §8.2; UX-SH-04; UI-ISS-038): `rounded-lg px-4 py-2.5
 * text-sm`, an optional icon, the message (AlertTitle and AlertDescription, or plain text), one
 * action and an optional Dismiss.
 *
 * - Text meets 4.5:1 on every soft fill, over `panel` and over `canvas` (alert.test.tsx measures
 *   it from the tokens).
 * - With an action or a Dismiss, the first line is as tall as the controls (28 px, 40 px on coarse
 *   pointers), so the icon, the first line of text, the action and Dismiss share a centre line.
 * - The action sits beside the message when the alert is at least 448 px wide, and under it
 *   (aligned with the text) when narrower, by the alert's own width (a container query).
 *
 *   <Alert tone="warning" urgent icon={<AlertTriangle />} action={<AlertAction>Reconnect</AlertAction>}>
 *     <AlertTitle>Instagram needs reconnecting</AlertTitle>
 *     <AlertDescription>New messages from @shop won't arrive until you reconnect.</AlertDescription>
 *   </Alert>
 */
function Alert({
  className,
  tone = "neutral",
  variant = "soft",
  urgent = false,
  icon,
  action,
  onDismiss,
  dismissLabel = "Dismiss",
  children,
  ...props
}: AlertProps) {
  const critical = urgent || tone === "danger"
  const dismissible = Boolean(onDismiss) && !critical
  // The first line matches a control's height when a control shares it: Dismiss always does, the
  // action only when it sits beside the message (the alert is `@md` wide or more).
  const line = dismissible
    ? "h-7 pointer-coarse:h-10"
    : action
      ? "h-5 @md/alert:h-7 @md/alert:pointer-coarse:h-10"
      : "h-5"
  const textPad = dismissible
    ? "py-1 pointer-coarse:py-2.5"
    : action
      ? "@md/alert:py-1 @md/alert:pointer-coarse:py-2.5"
      : ""

  return (
    <div
      data-slot="alert"
      data-tone={tone}
      data-variant={variant}
      data-urgent={critical || undefined}
      role={critical ? "alert" : "status"}
      className={cn(alertVariants({ variant, tone }), className)}
      {...props}
    >
      {icon ? (
        <span
          data-slot="alert-icon"
          aria-hidden
          className={cn(
            "flex shrink-0 items-center [&>svg]:size-4 [&>svg]:shrink-0",
            line,
            variant === "outline" && toneText(tone)
          )}
        >
          {icon}
        </span>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col items-start gap-2 @md/alert:flex-row @md/alert:gap-3">
        <div data-slot="alert-content" className={cn("w-full min-w-0 space-y-0.5 @md/alert:w-auto @md/alert:flex-1", textPad)}>
          {children}
        </div>
        {action ? (
          <div data-slot="alert-action" className="flex shrink-0 items-center gap-2">
            {action}
          </div>
        ) : null}
      </div>
      {dismissible ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          data-slot="alert-dismiss"
          aria-label={dismissLabel}
          onClick={onDismiss}
        >
          <X aria-hidden />
        </Button>
      ) : null}
    </div>
  )
}

/** The alert's title: the Item title role (14 px semibold); `fg` on `outline` and neutral alerts. */
function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "font-semibold group-data-[tone=neutral]/alert:text-fg group-data-[variant=outline]/alert:text-fg",
        className
      )}
      {...props}
    />
  )
}

/** The message under the title: the tone's colour on `soft`, `fg-secondary` on `outline`. */
function AlertDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn("group-data-[variant=outline]/alert:text-fg-secondary", className)}
      {...props}
    />
  )
}

/**
 * The alert's one action: Button `secondary` `sm` on every tone (DESIGN_SYSTEM §8.5: no tinted
 * variant), 40 px on coarse pointers. Wrap a Link with `asChild`.
 */
function AlertAction(props: Omit<React.ComponentProps<typeof Button>, "variant" | "size">) {
  return <Button variant="secondary" size="sm" {...props} />
}

export { Alert, AlertAction, AlertDescription, AlertTitle, alertVariants }
export type { AlertProps, AlertVariant }
