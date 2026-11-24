"use client"

import * as React from "react"
import { CalendarIcon, ChevronDownIcon, ClockIcon, XIcon } from "lucide-react"
import type { VariantProps } from "class-variance-authority"

import { Calendar } from "@/components/ui/calendar"
import { Field, FieldLabel, useFieldControl } from "@/components/ui/field"
import { Input, inputVariants } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { dayLabel, formatDay, parseDay } from "@/lib/day"
import { cn } from "@/lib/utils"

/**
 * Date and time pickers whose values are the strings the forms already keep: a day is
 * "YYYY-MM-DD", a time "HH:mm", both in the workspace's zone and neither carrying one. They replace
 * the native `date` and `time` inputs one for one, so a form submits exactly what it did (lib/tz
 * turns the pair into an instant, as before). Inside a Field they take its id, label,
 * `aria-describedby`, `aria-invalid` and `disabled`, like Input.
 */

type DatePickerProps = VariantProps<typeof inputVariants> & {
  /** "YYYY-MM-DD", or "" for no day yet. */
  value: string
  onChange: (value: string) => void
  /** The earliest and latest day that can be picked ("YYYY-MM-DD"); other days are disabled. */
  min?: string
  max?: string
  /** Today in the workspace's zone ("YYYY-MM-DD"); the browser's today when omitted. */
  today?: string
  /**
   * A month and a year Select in the calendar's caption, for a field where a far date is allowed.
   * Years run from `min` to `max`; a side without a bound reaches 10 years from today or from the
   * chosen day, whichever is further.
   */
  jumpMonths?: boolean
  placeholder?: string
  /** Shows a clear button while a day is chosen; clearing calls `onChange("")`. */
  clearable?: boolean
  clearLabel?: string
  id?: string
  disabled?: boolean
  className?: string
  "aria-label"?: string
  "aria-describedby"?: string
  "aria-invalid"?: React.AriaAttributes["aria-invalid"]
}

/** The months a jump-to Select offers: the allowed days, or 10 years around today and the chosen day. */
function yearBounds(min?: Date, max?: Date, selected?: Date, today?: Date) {
  const base = today ?? new Date()
  const years = [base.getFullYear(), selected?.getFullYear() ?? base.getFullYear()]
  const first = min ?? new Date(Math.min(...years) - 10, 0, 1)
  const last = max ?? new Date(Math.max(...years) + 10, 11, 31)
  return { start: new Date(first.getFullYear(), first.getMonth(), 1), end: new Date(last.getFullYear(), last.getMonth(), 1) }
}

/**
 * A button on the Input recipe that shows the chosen day and opens a calendar. Choosing a day
 * closes it; Esc closes it too and focus returns to the button.
 */
function DatePicker({
  value,
  onChange,
  min,
  max,
  today,
  jumpMonths = false,
  placeholder = "Pick a date",
  clearable = false,
  clearLabel = "Clear date",
  size = "default",
  className,
  ...props
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false)
  const fieldProps = useFieldControl(props)
  const selected = parseDay(value)
  const minDay = parseDay(min)
  const maxDay = parseDay(max)
  const label = dayLabel(value)
  const todayDay = parseDay(today)
  const clear = clearable && Boolean(label)
  const reach = jumpMonths ? yearBounds(minDay, maxDay, selected, todayDay) : null
  return (
    <div className="relative w-full">
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-slot="date-picker"
          data-size={size}
          data-placeholder={label ? undefined : ""}
          className={cn(
            inputVariants({ size }),
            "flex w-full items-center gap-2 text-left whitespace-nowrap select-none data-placeholder:text-fg-secondary [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
            clear && "pr-9",
            className
          )}
          {...props}
          {...fieldProps}
        >
          <CalendarIcon aria-hidden className="text-fg-secondary" />
          <span className="min-w-0 flex-1 truncate">{label ?? placeholder}</span>
          {clear ? null : <ChevronDownIcon aria-hidden className="text-fg-secondary" />}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-auto p-2"
        // Land on the chosen day (or today), so the arrow keys start where the eye is.
        onOpenAutoFocus={(event) => {
          const content = event.currentTarget as HTMLElement
          const day = content.querySelector<HTMLElement>("td button[tabindex='0']")
          if (day) {
            event.preventDefault()
            day.focus()
          }
        }}
      >
        <Calendar
          mode="single"
          required
          selected={selected}
          defaultMonth={selected ?? todayDay}
          today={todayDay}
          showOutsideDays={false}
          {...(reach ? { captionLayout: "dropdown" as const, startMonth: reach.start, endMonth: reach.end } : null)}
          disabled={[...(minDay ? [{ before: minDay }] : []), ...(maxDay ? [{ after: maxDay }] : [])]}
          onSelect={(day) => {
            if (!day) return
            onChange(formatDay(day))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
    {clear ? (
      <button
        type="button"
        aria-label={clearLabel}
        onClick={() => onChange("")}
        className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-fg-secondary hover:text-fg"
      >
        <XIcon aria-hidden className="size-4" />
      </button>
    ) : null}
    </div>
  )
}

const TIME_STRICT = /^(\d{1,2}):(\d{2})$/
const TIME_LENIENT = /^(\d{1,2})(?::?(\d{2}))?$/

/** "9:30" is "09:30"; with `lenient`, "930" and "9" are times too. Null when it isn't a time of day. */
function parseTime(text: string, lenient = false): string | null {
  const trimmed = text.trim()
  const match = (lenient ? TIME_LENIENT : TIME_STRICT).exec(lenient && /^\d{3,4}$/.test(trimmed) ? `${trimmed.slice(0, -2)}:${trimmed.slice(-2)}` : trimmed)
  if (!match) return null
  const hours = Number(match[1])
  const minutes = Number(match[2] ?? 0)
  if (hours > 23 || minutes > 59) return null
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`
}

const HOURS = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, "0"))
const MINUTES = Array.from({ length: 60 }, (_, minute) => String(minute).padStart(2, "0"))

type TimeFieldProps = Omit<React.ComponentProps<typeof Input>, "value" | "onChange" | "type"> & {
  /** "HH:mm", or "" for none. */
  value: string
  /** Called with a complete "HH:mm" as soon as one is typed or picked, and "" when cleared. */
  onChange: (value: string) => void
  /** The earliest time in the list ("HH:mm"); earlier ones are shown disabled. A typed time is the form's to check. */
  min?: string
}

/**
 * A time of day: a text input that takes any minute ("18:07", "930") and shows it as HH:mm once you
 * leave it, with an hour column and a minute column beside it to pick any minute. The native `time` input's
 * value format, without its per-browser 12/24-hour widget. Inside a Field it is the labelled
 * control, so `getByLabelText("Time")` finds the input.
 */
function TimeField({ value, onChange, min, className, size = "default", disabled: disabledProp, onBlur, ...props }: TimeFieldProps) {
  const fieldDisabled = useFieldControl(props).disabled
  const disabled = disabledProp ?? fieldDisabled
  const [draft, setDraft] = React.useState<string | null>(null)
  const [open, setOpen] = React.useState(false)
  const [previous, setPrevious] = React.useState(value)
  if (previous !== value) {
    // Changed from outside (a picked slot, a reset): drop what was typed unless it says the same.
    setPrevious(value)
    if (draft !== null && (parseTime(draft) ?? "") !== value) setDraft(null)
  }
  return (
    <div className="relative w-full">
      <Input
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder="HH:mm"
        size={size}
        disabled={disabled}
        className={cn("pr-9 tabular-nums", className)}
        {...props}
        value={draft ?? value}
        onChange={(event) => {
          const text = event.target.value
          setDraft(text)
          const time = parseTime(text)
          if (time) onChange(time)
          else if (text.trim() === "") onChange("")
        }}
        onBlur={(event) => {
          const time = draft === null ? null : parseTime(draft, true)
          if (time && time !== value) onChange(time)
          setDraft(null)
          onBlur?.(event)
        }}
      />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            aria-label="Choose a time"
            className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-fg-secondary hover:text-fg disabled:pointer-events-none disabled:opacity-50"
          >
            <ClockIcon aria-hidden className="size-4" />
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          className="w-auto gap-0 p-1"
          onOpenAutoFocus={(event) => {
            const content = event.currentTarget as HTMLElement
            event.preventDefault()
            // Each column shows its chosen value; focus starts on the hour.
            for (const list of content.querySelectorAll<HTMLElement>("[role='listbox']")) {
              list.querySelector<HTMLElement>("[aria-selected='true']")?.scrollIntoView?.({ block: "center" })
            }
            const current =
              content.querySelector<HTMLElement>("[aria-label='Hours'] [aria-selected='true']:not([aria-disabled='true'])") ??
              content.querySelector<HTMLElement>("[role='option']:not([aria-disabled='true'])")
            current?.focus()
          }}
        >
          <TimeColumns
            min={min}
            value={value}
            onPick={(time, done) => {
              onChange(time)
              setDraft(null)
              if (done) setOpen(false)
            }}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}

/**
 * An hour column and a minute column, each a listbox: arrows move, Enter or a click chooses. Picking
 * an hour keeps the minute (or the earliest allowed one) and leaves the columns open; picking a
 * minute sets the time and closes them. Times before `min` are disabled.
 */
function TimeColumns({ min, value, onPick }: { min?: string; value: string; onPick: (time: string, done: boolean) => void }) {
  const minHour = min?.slice(0, 2)
  const minMinute = min?.slice(3, 5)
  const [hour, setHour] = React.useState<string | null>(value ? value.slice(0, 2) : null)
  const minute = value ? value.slice(3, 5) : null
  const shownHour = hour ?? minHour ?? HOURS.find((h) => !minHour || h >= minHour) ?? "00"
  const earliestIn = (h: string) => (minHour && h === minHour && minMinute ? minMinute : "00")
  const pickHour = (h: string) => {
    setHour(h)
    const m = minute && `${h}:${minute}` >= (min ?? "") ? minute : earliestIn(h)
    onPick(`${h}:${m}`, false)
  }
  return (
    <div className="flex gap-1">
      <TimeColumn
        label="Hours"
        items={HOURS}
        isSelected={(h) => h === (hour ?? (value ? value.slice(0, 2) : null))}
        isDisabled={(h) => Boolean(minHour && h < minHour)}
        onPick={pickHour}
      />
      <TimeColumn
        label="Minutes"
        items={MINUTES}
        isSelected={(m) => m === minute && shownHour === value.slice(0, 2)}
        isDisabled={(m) => Boolean(min && `${shownHour}:${m}` < min)}
        onPick={(m) => onPick(`${shownHour}:${m}`, true)}
      />
    </div>
  )
}

function TimeColumn({
  label,
  items,
  isSelected,
  isDisabled,
  onPick,
}: {
  label: string
  items: string[]
  isSelected: (item: string) => boolean
  isDisabled: (item: string) => boolean
  onPick: (item: string) => void
}) {
  const move = (event: React.KeyboardEvent<HTMLUListElement>) => {
    const options = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("[role='option']:not([aria-disabled='true'])"))
    const index = options.indexOf(document.activeElement as HTMLElement)
    const target = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: options.length - 1 }[event.key]
    if (target === undefined) return
    event.preventDefault()
    options[Math.max(0, Math.min(options.length - 1, target))]?.focus()
  }
  return (
    <div className="w-14">
    {/* Both columns count from 00, so each says what it is; the listbox's name says it to screen readers. */}
    <p aria-hidden className="px-2 pb-1 text-center text-xs font-medium text-fg-secondary">{label === "Hours" ? "Hour" : "Min"}</p>
    <ul role="listbox" aria-label={label} onKeyDown={move} className="max-h-56 overflow-y-auto">
      {items.map((item) => {
        const disabled = isDisabled(item)
        return (
          <li
            key={item}
            role="option"
            aria-selected={isSelected(item)}
            aria-disabled={disabled || undefined}
            tabIndex={-1}
            onClick={disabled ? undefined : () => onPick(item)}
            onKeyDown={(event) => {
              if (!disabled && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault()
                onPick(item)
              }
            }}
            className="cursor-default aria-disabled:pointer-events-none aria-disabled:opacity-40 rounded-md px-2 py-1 text-center text-sm tabular-nums hover:bg-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand aria-selected:bg-brand-soft aria-selected:text-brand-fg pointer-coarse:min-h-10 pointer-coarse:py-2"
          >
            {item}
          </li>
        )
      })}
    </ul>
    </div>
  )
}

type DateTimePickerProps = {
  value: { date: string; time: string }
  onChange: (value: { date: string; time: string }) => void
  /** Ids of the two controls: `${idPrefix}-date` and `${idPrefix}-time`. */
  idPrefix: string
  min?: string
  max?: string
  /** The earliest time on the `min` day ("HH:mm"); earlier times there are disabled in the list. */
  minTime?: string
  today?: string
  /** See DatePicker: a month and year Select for far dates. */
  jumpMonths?: boolean
  size?: "sm" | "default" | "lg" | "xl"
  density?: "default" | "compact"
  /** Keeps the labels for screen readers only. */
  hideLabels?: boolean
  labels?: { date: string; time: string }
  labelClassName?: string
  invalid?: boolean
  disabled?: boolean
  /** Disables the time until a day is chosen. */
  timeNeedsDate?: boolean
  className?: string
}

/**
 * A day and a time side by side, each in its own labelled Field (the id prefix names them). The
 * pair is `{ date, time }`, the shape ScheduleFields and the other schedule forms already hold.
 */
function DateTimePicker({
  value,
  onChange,
  idPrefix,
  min,
  max,
  minTime,
  today,
  jumpMonths,
  size = "lg",
  density = "default",
  hideLabels = false,
  labels = { date: "Date", time: "Time" },
  labelClassName,
  invalid,
  disabled,
  timeNeedsDate = false,
  className,
}: DateTimePickerProps) {
  const labelClass = cn(hideLabels && "sr-only", labelClassName)
  return (
    <div className={cn("grid grid-cols-[minmax(0,1fr)_minmax(0,9rem)] gap-2", className)}>
      <Field id={`${idPrefix}-date`} density={density} invalid={invalid} disabled={disabled}>
        <FieldLabel className={labelClass}>{labels.date}</FieldLabel>
        <DatePicker size={size} value={value.date} min={min} max={max} today={today} jumpMonths={jumpMonths} onChange={(date) => onChange({ ...value, date })} />
      </Field>
      <Field id={`${idPrefix}-time`} density={density} invalid={invalid} disabled={disabled || (timeNeedsDate && !value.date)}>
        <FieldLabel className={labelClass}>{labels.time}</FieldLabel>
        <TimeField
          size={size}
          value={value.time}
          // A day before the first allowed one has no time left ("24:00" is after every time); the first day starts at minTime.
          min={value.date && min ? (value.date < min ? "24:00" : value.date === min ? minTime : undefined) : undefined}
          onChange={(time) => onChange({ ...value, time })}
        />
      </Field>
    </div>
  )
}

export { DatePicker, DateTimePicker, TimeField, parseTime }
