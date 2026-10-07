import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

export type StepState = "complete" | "incomplete" | "error";

const STATE_TEXT: Record<StepState, string> = {
  complete: "complete",
  incomplete: "not finished",
  error: "needs attention",
};

/**
 * UX-SCR-03: one step of the editor. A bg-panel card with a micro label and a 10 px node in the
 * left gutter: brand when complete, danger when activation found a problem. The editor draws the
 * gutter line; the card is focusable so the editor can take the user to it.
 */
export function StepCard({
  id,
  label,
  state,
  errors = [],
  action,
  children,
}: {
  id: string;
  label: string;
  state: StepState;
  /** Activation or save errors for this step's fields (FR-AUT-02). */
  errors?: string[];
  /** A control on the right of the label, e.g. Settings' Edit. */
  action?: ReactNode;
  children: ReactNode;
}) {
  const labelId = `step-${id}-label`;
  return (
    <section
      id={`step-${id}`}
      data-step={id}
      data-state={state}
      aria-labelledby={labelId}
      tabIndex={-1}
      className={cn(
        "relative scroll-mt-24 rounded-xl border bg-panel p-5",
        state === "error" ? "border-danger" : "border-line",
      )}
    >
      <span
        aria-hidden
        data-node={state}
        className={cn(
          "absolute top-6 -left-[25px] size-2.5 rounded-full ring-2 ring-canvas",
          state === "complete" && "bg-brand",
          state === "error" && "bg-danger",
          state === "incomplete" && "bg-raised-hover",
        )}
      />
      <div className="mb-4 flex min-h-6 items-center justify-between gap-3">
        <h2 id={labelId} className={EYEBROW}>
          {label}
          <span className="sr-only">, {STATE_TEXT[state]}</span>
        </h2>
        {action}
      </div>
      {errors.length > 0 ? (
        <ul className="mb-4 space-y-1 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger-fg">
          {errors.map((message) => (
            <li key={message} className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>{message}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {children}
    </section>
  );
}

/** Focus a step: its first field when it has one (the gallery opens on the first incomplete step). */
export function focusStep(id: string, { field = true }: { field?: boolean } = {}): void {
  const section = document.getElementById(`step-${id}`);
  if (!section) return;
  const target = field
    ? section.querySelector<HTMLElement>(
        "input:not([disabled]):not([type=hidden]), textarea:not([disabled]), button[role=radio][data-state=on], button[role=combobox], button:not([disabled])",
      )
    : null;
  (target ?? section).focus();
  section.scrollIntoView?.({ block: "center", behavior: "smooth" });
}
