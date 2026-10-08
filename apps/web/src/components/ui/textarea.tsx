"use client"

import * as React from "react"

import { useFieldControl } from "@/components/ui/field"
import { fieldControlClass } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/** Input's field look (surface, edge, text size, focus, invalid), grown to its content. */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  const fieldProps = useFieldControl(props)
  return (
    <textarea
      data-slot="textarea"
      className={cn(fieldControlClass, "flex field-sizing-content min-h-20 py-2 leading-relaxed", className)}
      {...props}
      {...fieldProps}
    />
  )
}

export { Textarea }
