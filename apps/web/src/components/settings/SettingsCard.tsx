import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

/** A section label inside a card ("ALWAYS BUILT IN"): the one eyebrow style (DESIGN_SYSTEM §2.1). */
export function SectionLabel({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
  return (
    <p id={id} className={cn(EYEBROW, className)}>
      {children}
    </p>
  );
}

/**
 * The settings card (C-066): a rounded panel named by its heading (a region for assistive tech),
 * with an optional icon, section label, one-line description and something on the right. The
 * danger tone is the red-accented card of the workspace's danger zone.
 */
export function SettingsCard({
  id,
  title,
  label,
  description,
  icon,
  aside,
  tone = "default",
  className,
  children,
}: {
  id: string;
  title: ReactNode;
  label?: string;
  description?: ReactNode;
  icon?: ReactNode;
  aside?: ReactNode;
  tone?: "default" | "danger";
  className?: string;
  children?: ReactNode;
}) {
  return (
    <section
      aria-labelledby={`${id}-title`}
      className={cn(
        "min-w-0 rounded-2xl border bg-panel p-5 md:p-6",
        tone === "danger" ? "border-danger/40 border-l-4 border-l-danger" : "border-line",
        className,
      )}
    >
      <div className={cn("flex items-start justify-between gap-3", children ? "mb-5" : null)}>
        <div className="flex min-w-0 items-start gap-3">
          {icon ? (
            <span
              aria-hidden
              className={cn(
                "grid size-10 shrink-0 place-items-center rounded-xl [&_svg]:size-5",
                tone === "danger" ? "bg-danger-soft text-danger-fg" : "bg-raised text-brand-fg",
              )}
            >
              {icon}
            </span>
          ) : null}
          <div className="min-w-0 space-y-1">
            {label ? <SectionLabel>{label}</SectionLabel> : null}
            <h2
              id={`${id}-title`}
              className={cn("text-base font-semibold", tone === "danger" && "text-danger-fg")}
            >
              {title}
            </h2>
            {description ? <p className="text-sm text-fg-secondary">{description}</p> : null}
          </div>
        </div>
        {aside ? <div className="shrink-0">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}
