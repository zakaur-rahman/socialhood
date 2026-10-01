"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

/**
 * Field: shadcn's Field (label, control, description, error), the one way to lay out a form field
 * (DESIGN_SYSTEM §8.2, §10 item 5). On top of shadcn's layout it wires the control:
 *
 * - the control gets the Field's id (`id`, or a generated one) and FieldLabel points at it;
 * - every FieldDescription and FieldError inside is listed in the control's `aria-describedby`,
 *   descriptions first, while it is shown;
 * - the control is `aria-invalid` while a FieldError shows (or when `invalid` is set);
 * - `disabled` disables the control and dims the label.
 *
 * Input, Textarea, Checkbox and Switch wire themselves; wrap any other control in FieldControl.
 * A control with its own `id` that differs from the Field's is left alone (one control per Field).
 *
 *   <Field>
 *     <FieldLabel>Workspace name</FieldLabel>
 *     <Input {...register("name")} />
 *     <FieldDescription>Shown to your team.</FieldDescription>
 *     <FieldError>{errors.name?.message}</FieldError>
 *   </Field>
 *
 * `density="compact"` is for compact forms (inbox and schedule popovers): 12 px labels in
 * fg-secondary (DESIGN_SYSTEM §2.2). Fields stack in a FieldGroup, 16 px apart (§3).
 */

type Density = "default" | "compact"
type Part = "description" | "error"

type FieldContextValue = {
  controlId: string
  describedBy: string | undefined
  invalid: boolean
  disabled: boolean
  density: Density
  register: (part: Part, id: string) => () => void
}

const FieldContext = React.createContext<FieldContextValue | null>(null)

const fieldVariants = cva("group/field flex w-full", {
  variants: {
    orientation: {
      // Label to control 6 px (DESIGN_SYSTEM §3: "label to control space-y-1.5").
      vertical: "flex-col gap-1.5",
      // A checkbox or switch beside its label (and description, in a FieldContent).
      horizontal: "flex-row items-center gap-3 has-[>[data-slot=field-content]]:items-start",
    },
  },
  defaultVariants: { orientation: "vertical" },
})

function Field({
  id,
  invalid,
  disabled = false,
  density = "default",
  orientation = "vertical",
  className,
  children,
  ...props
}: React.ComponentProps<"div"> &
  VariantProps<typeof fieldVariants> & {
    /** The control's id; generated when omitted. */
    id?: string
    /** Marks the control invalid; by default it is invalid while a FieldError shows. */
    invalid?: boolean
    disabled?: boolean
    density?: Density
  }) {
  const generatedId = React.useId()
  const controlId = id ?? generatedId
  const [parts, setParts] = React.useState<ReadonlyArray<{ part: Part; id: string }>>([])

  const register = React.useCallback((part: Part, partId: string) => {
    setParts((list) => [...list, { part, id: partId }])
    return () => setParts((list) => list.filter((entry) => !(entry.part === part && entry.id === partId)))
  }, [])

  const hasError = parts.some((entry) => entry.part === "error")
  const describedBy =
    [...parts.filter((entry) => entry.part === "description"), ...parts.filter((entry) => entry.part === "error")]
      .map((entry) => entry.id)
      .join(" ") || undefined
  const isInvalid = invalid ?? hasError

  const value = React.useMemo<FieldContextValue>(
    () => ({ controlId, describedBy, invalid: isInvalid, disabled, density, register }),
    [controlId, describedBy, isInvalid, disabled, density, register]
  )

  return (
    <FieldContext.Provider value={value}>
      <div
        role="group"
        data-slot="field"
        data-orientation={orientation}
        data-density={density}
        data-invalid={isInvalid ? "true" : undefined}
        data-disabled={disabled ? "true" : undefined}
        className={cn(fieldVariants({ orientation }), className)}
        {...props}
      >
        {children}
      </div>
    </FieldContext.Provider>
  )
}

type ControlProps = {
  id?: string
  disabled?: boolean
  "aria-describedby"?: string
  "aria-invalid"?: React.AriaAttributes["aria-invalid"]
}

/**
 * The props a control inside a Field takes from it: `id`, `aria-describedby` (its own ids first,
 * then the Field's descriptions and errors), `aria-invalid` and `disabled`. Spread the result after
 * the control's own props. Outside a Field, or for a control whose own `id` isn't the Field's, it
 * returns nothing.
 */
function useFieldControl(props: ControlProps): ControlProps {
  const field = React.useContext(FieldContext)
  if (!field || (props.id !== undefined && props.id !== field.controlId)) return {}
  const describedBy = [...new Set([props["aria-describedby"], field.describedBy].join(" ").split(" ").filter(Boolean))]
  return {
    id: field.controlId,
    "aria-describedby": describedBy.length > 0 ? describedBy.join(" ") : undefined,
    "aria-invalid": props["aria-invalid"] ?? (field.invalid ? true : undefined),
    disabled: props.disabled ?? (field.disabled || undefined),
  }
}

/**
 * Wires any other control (a select trigger, a custom picker) into its Field. Put `id` and ARIA
 * props on FieldControl, not on the child: the child's own props win over what it passes down.
 */
function FieldControl(props: React.ComponentProps<typeof Slot.Root>) {
  const fieldProps = useFieldControl(props as ControlProps)
  return <Slot.Root {...props} {...fieldProps} />
}

/** Registers a description or error with its Field while it is shown. */
function useFieldPart(part: Part, idProp: string | undefined) {
  const field = React.useContext(FieldContext)
  const generatedId = React.useId()
  const id = idProp ?? generatedId
  const register = field?.register
  React.useLayoutEffect(() => register?.(part, id), [register, part, id])
  return id
}

/** Fields stacked 16 px apart (DESIGN_SYSTEM §3: "fields space-y-4"). */
function FieldGroup({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="field-group" className={cn("flex w-full flex-col gap-4", className)} {...props} />
}

/** In a horizontal Field: the label and description beside the control. */
function FieldContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="field-content" className={cn("flex min-w-0 flex-1 flex-col gap-1", className)} {...props} />
}

function FieldLabel({ className, htmlFor, ...props }: React.ComponentProps<typeof Label>) {
  const field = React.useContext(FieldContext)
  return (
    <Label
      data-slot="field-label"
      htmlFor={htmlFor ?? field?.controlId}
      className={cn(
        "group-data-[disabled=true]/field:opacity-50",
        field?.density === "compact" && "text-xs text-fg-secondary",
        className
      )}
      {...props}
    />
  )
}

function FieldDescription({ className, id, ...props }: React.ComponentProps<"p">) {
  const partId = useFieldPart("description", id)
  return <p data-slot="field-description" id={partId} className={cn("text-xs text-fg-secondary", className)} {...props} />
}

type FieldErrorProps = React.ComponentProps<"div"> & {
  /** Validation errors (react-hook-form's, for example); repeated messages show once. */
  errors?: ReadonlyArray<{ message?: string } | undefined>
}

/** The error, in danger-fg text (DESIGN_SYSTEM §8.3); renders nothing without a message. */
function FieldError({ children, errors, ...props }: FieldErrorProps) {
  let content: React.ReactNode = children
  if (!content && errors?.length) {
    const messages = [...new Set(errors.map((error) => error?.message).filter((message): message is string => Boolean(message)))]
    content =
      messages.length > 1 ? (
        <ul className="ml-4 flex list-disc flex-col gap-1">
          {messages.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : (
        messages[0]
      )
  }
  if (!content) return null
  return <FieldErrorMessage {...props}>{content}</FieldErrorMessage>
}

function FieldErrorMessage({ className, id, ...props }: React.ComponentProps<"div">) {
  const partId = useFieldPart("error", id)
  return <div role="alert" data-slot="field-error" id={partId} className={cn("text-xs text-danger-fg", className)} {...props} />
}

export { Field, FieldContent, FieldControl, FieldDescription, FieldError, FieldGroup, FieldLabel, useFieldControl }
