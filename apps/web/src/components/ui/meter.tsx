"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * What a meter measures (DESIGN_SYSTEM §8.2; UI-ISS-037, VH-007):
 * - `consumable`: something used up and renewed, like AI credits, scheduled posts this month or
 *   knowledge characters. It warns at 80% and is full, in danger, at 100%.
 * - `slot`: a number of places, like connected accounts or active automations. Filling them is
 *   normal use, so it never warns and at 100% it says a neutral "All used".
 */
export type MeterKind = "consumable" | "slot"

/** `full` is 100% or more of the limit; `warning` is 80% or more of a consumable. */
export type MeterLevel = "normal" | "warning" | "full"

/** The share of a consumable's limit from which its meter warns. */
export const METER_WARNING = 0.8

/**
 * The one threshold rule for usage (UX-SCR-07): full at 100% of the limit, and for consumables a
 * warning from 80%. No limit (null, undefined or 0) is always normal.
 */
export function meterLevel(used: number, limit: number | null | undefined, kind: MeterKind = "consumable"): MeterLevel {
  if (!limit) return "normal"
  const share = used / limit
  if (share >= 1) return "full"
  if (kind === "consumable" && share >= METER_WARNING) return "warning"
  return "normal"
}

type Tone = "normal" | "warning" | "danger"

/** A slot that is full stays neutral: having every place in use isn't an error. */
function meterTone(level: MeterLevel, kind: MeterKind): Tone {
  if (level === "full") return kind === "slot" ? "normal" : "danger"
  return level
}

// Status colours straight from the tokens (UI-016's tone map isn't on develop yet). The bar is the
// decor gradient (§1.9); the ring's 3 px arc is a mark under 12 px, so it is solid brand.
const FILL: Record<Tone, string> = { normal: "bg-brand-gradient-decor", warning: "bg-warning", danger: "bg-danger" }
const ARC: Record<Tone, string> = { normal: "stroke-brand", warning: "stroke-warning", danger: "stroke-danger" }
const FIGURE: Record<Tone, string> = { normal: "text-fg-secondary", warning: "text-warning", danger: "text-danger-fg" }

const count = new Intl.NumberFormat("en-US")

/**
 * The ring's figure: rounded down, so it reads 100% only when the meter is full, and "<1%" for a
 * little use rather than a "0%" that looks unused.
 */
function percentText(value: number, max: number): string {
  const share = (value / max) * 100
  if (value > 0 && share < 1) return "<1%"
  return `${Math.min(999, Math.max(0, Math.floor(share)))}%`
}

type MeterProps = Omit<React.ComponentProps<"div">, "children"> & {
  /** What is measured ("AI credits"); it names the meter. */
  label: React.ReactNode
  value: number
  /** The limit. null or undefined (or 0): no limit, so no bar, and the text says "no limit". */
  max: number | null | undefined
  /** After the numbers: "credits" gives "412 of 500 credits". */
  unit?: string
  kind?: MeterKind
  /** Replaces the value text ("{value} of {max} {unit}"), on screen and for assistive tech. */
  valueText?: string
  /**
   * `bar` (default): the label and value text over a 6 px bar. `ring`: a compact 40 px ring with
   * the percentage inside, for tight spaces (the collapsed sidebar); its label is for assistive
   * tech only, so show the numbers nearby or in a tooltip. Without a limit the ring renders nothing.
   */
  variant?: "bar" | "ring"
  /** At 100%: which limit was reached, to say what to do (§4.1), e.g. "Free includes 1 account". */
  fullMessage?: React.ReactNode
  /** At 100%, after the message: one action, e.g. an Upgrade link. */
  action?: React.ReactNode
}

/**
 * Meter: usage against a limit (`role="meter"`), for credits, quotas and scores (§8.2). Track
 * `raised`, 6 px; fill the decor gradient, `warning` from 80% and `danger` at 100% for
 * consumables; a slot at 100% stays brand and says "All used". The value text is on screen and is
 * the meter's `aria-valuetext`; the message at 100% describes it. The root carries `data-level`
 * and `data-kind`.
 *
 *   <Meter label="AI credits" value={412} max={500} unit="credits" />
 *   <Meter label="Instagram accounts" kind="slot" value={1} max={1} unit="accounts"
 *     fullMessage="Free includes 1 account per platform." action={<Link href={…}>Upgrade</Link>} />
 *
 * Task progress (uploads, analysis) is Progress, not Meter.
 */
function Meter({
  label,
  value,
  max,
  unit,
  kind = "consumable",
  valueText,
  variant = "bar",
  fullMessage,
  action,
  className,
  ...props
}: MeterProps) {
  const id = React.useId()
  const labelId = `${id}-label`
  const fullId = `${id}-full`
  const limit = typeof max === "number" && max > 0 ? max : null
  const level = meterLevel(value, limit, kind)
  const tone = meterTone(level, kind)
  const units = unit ? ` ${unit}` : ""
  const text =
    valueText ?? (limit ? `${count.format(value)} of ${count.format(limit)}${units}` : `${count.format(value)}${units} · no limit`)
  const share = limit ? Math.min(1, Math.max(0, value / limit)) : 0
  const meterAria = limit
    ? {
        role: "meter",
        "aria-labelledby": labelId,
        "aria-valuemin": 0,
        "aria-valuemax": limit,
        "aria-valuenow": Math.max(0, Math.min(value, limit)),
        "aria-valuetext": text,
      }
    : null

  if (variant === "ring") {
    if (!meterAria || limit === null) return null
    const radius = 17
    const circumference = 2 * Math.PI * radius
    return (
      <div
        data-slot="meter"
        data-variant="ring"
        data-kind={kind}
        data-level={level}
        className={cn("relative grid size-10 shrink-0 place-items-center", className)}
        {...meterAria}
        {...props}
      >
        <span id={labelId} className="sr-only">
          {label}
        </span>
        <svg viewBox="0 0 40 40" className="absolute inset-0 size-full -rotate-90" aria-hidden>
          <circle cx="20" cy="20" r={radius} fill="none" strokeWidth="3" className="stroke-raised" />
          {share > 0 ? (
            <circle
              data-slot="meter-fill"
              cx="20"
              cy="20"
              r={radius}
              fill="none"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - share)}
              className={cn(
                "transition-[stroke-dashoffset] duration-500 ease-standard motion-reduce:transition-none",
                ARC[tone]
              )}
            />
          ) : null}
        </svg>
        <span aria-hidden className={cn("relative text-2xs font-medium tabular-nums", FIGURE[tone])}>
          {percentText(value, limit)}
        </span>
      </div>
    )
  }

  const full = level === "full" && (kind === "slot" || fullMessage !== undefined || action !== undefined)
  return (
    <div
      data-slot="meter"
      data-variant="bar"
      data-kind={kind}
      data-level={level}
      className={cn("flex min-w-0 flex-col gap-1.5", className)}
      {...props}
    >
      <div className="flex items-baseline justify-between gap-3 text-xs">
        <span id={labelId} className="min-w-0 text-fg-secondary">
          {label}
        </span>
        <span data-slot="meter-value" className={cn("shrink-0 tabular-nums", FIGURE[tone])}>
          {text}
        </span>
      </div>
      {meterAria ? (
        <div
          {...meterAria}
          aria-describedby={full ? fullId : undefined}
          className="h-1.5 overflow-hidden rounded-full bg-raised"
        >
          <div
            data-slot="meter-fill"
            className={cn(
              "h-full rounded-full transition-[width] duration-500 ease-standard motion-reduce:transition-none",
              FILL[tone]
            )}
            style={{ width: `${share * 100}%` }}
          />
        </div>
      ) : null}
      {full ? (
        <p
          id={fullId}
          className={cn(
            "flex flex-wrap items-center gap-x-2 gap-y-1 text-xs",
            kind === "slot" ? "text-fg-secondary" : "text-danger-fg"
          )}
        >
          {/* The spaces keep the words apart in the description; the flex gap spaces them on screen. */}
          {kind === "slot" ? <span className="font-medium text-fg">All used</span> : null}{" "}
          {fullMessage}{" "}
          {action}
        </p>
      ) : null}
    </div>
  )
}

export { Meter }
