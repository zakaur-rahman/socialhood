import * as React from "react"

import { cn } from "@/lib/utils"

/** A progress bar always has a name: an `aria-label`, or the id of the text that says what runs. */
type ProgressName =
  | { "aria-label": string; "aria-labelledby"?: never }
  | { "aria-labelledby": string; "aria-label"?: never }

type ProgressProps = Omit<React.ComponentProps<"div">, "children" | "aria-label" | "aria-labelledby"> &
  ProgressName & {
    /** Done so far, from 0 to `max`. */
    value: number
    /** The total; 100 by default (a percentage). */
    max?: number
    /** What assistive tech reads instead of the bare number, e.g. "12,400 of 58,000 comments". */
    valueText?: string
  }

/**
 * Progress: a task on its way (`role="progressbar"`): uploads, comment analysis (DESIGN_SYSTEM
 * §8.2; UI-ISS-037). Usage against a limit is Meter. The same 6 px `raised` track and decor-gradient
 * fill as Meter (§1.9), with no thresholds; the fill moves in 150 ms (§7.2), at once under reduced
 * motion. Say what is happening in text beside it (a status line or the file name).
 *
 *   <Progress aria-label={`Uploading ${file.name}`} value={percent} />
 *   <Progress aria-labelledby="analysis-status" value={analysed} max={total} valueText={text} />
 */
function Progress({ value, max = 100, valueText, className, ...props }: ProgressProps) {
  const total = max > 0 ? max : 100
  const done = Math.max(0, Math.min(value, total))
  return (
    <div
      role="progressbar"
      data-slot="progress"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={done}
      aria-valuetext={valueText}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-raised", className)}
      {...props}
    >
      <div
        data-slot="progress-fill"
        className="bg-brand-gradient-decor h-full rounded-full transition-[width] duration-normal ease-standard motion-reduce:transition-none"
        style={{ width: `${(done / total) * 100}%` }}
      />
    </div>
  )
}

export { Progress }
