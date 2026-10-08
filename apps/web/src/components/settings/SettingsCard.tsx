import type { ReactNode } from "react";

import { Card, CardDescription, CardTitle } from "@/components/ui/card";
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
 * The settings card (C-066): a thin wrapper over Card (`roomy`, `rounded-xl` per D-02) named by its
 * heading (a region for assistive tech),
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
    <Card asChild padding="roomy" tone={tone === "danger" ? "danger" : "default"} className={cn("space-y-5", className)}>
      <section aria-labelledby={`${id}-title`}>
        <div className="flex items-start justify-between gap-3">
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
              <CardTitle id={`${id}-title`} className={cn(tone === "danger" && "text-danger-fg")}>
                {title}
              </CardTitle>
              {description ? <CardDescription>{description}</CardDescription> : null}
            </div>
          </div>
          {aside ? <div className="shrink-0">{aside}</div> : null}
        </div>
        {children}
      </section>
    </Card>
  );
}
