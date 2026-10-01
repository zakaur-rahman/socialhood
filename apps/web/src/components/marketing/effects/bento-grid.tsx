import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Bento Grid, from Aceternity UI's free "bento-grid" (ui.aceternity.com/components/bento-grid),
 * adapted for Social Hood (C-068):
 * - a list (ul/li) with an h3 per card, so the cards read as a list of features;
 * - surfaces, lines and text from the tokens; lucide icons instead of Tabler's (no new
 *   dependency);
 * - the hover lift moves the text, never the illustration, and only without reduced motion;
 * - each card enters on scroll through `data-reveal` (ScrollReveal), with a stagger.
 */
export function BentoGrid({ className, children, label }: { className?: string; children: ReactNode; label?: string }) {
  return (
    <ul aria-label={label} className={cn("mx-auto grid max-w-6xl grid-cols-1 gap-4 md:grid-cols-3", className)}>
      {children}
    </ul>
  );
}

export function BentoGridItem({
  className,
  title,
  description,
  header,
  icon,
  index = 0,
  note,
}: {
  className?: string;
  title: string;
  description: ReactNode;
  /** The illustration: decorative (aria-hidden by the caller). */
  header?: ReactNode;
  icon?: ReactNode;
  index?: number;
  note?: string;
}) {
  return (
    <li data-reveal style={{ "--reveal-delay": `${(index % 3) * 80}ms` } as CSSProperties} className={cn("min-w-0", className)}>
      <div className="group/bento flex h-full flex-col gap-5 rounded-2xl border border-line bg-panel p-4 transition-[border-color,box-shadow] duration-200 hover:border-line-strong hover:shadow-xl hover:shadow-brand/10 sm:p-5">
        {header}
        <div className="mt-auto transition-transform duration-200 motion-safe:group-hover/bento:translate-x-1">
          <div className="flex items-center gap-2">
            {icon}
            <h3 className="text-base font-semibold">{title}</h3>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{description}</p>
          {note ? <p className="mt-2 text-xs font-medium text-brand-fg">{note}</p> : null}
        </div>
      </div>
    </li>
  );
}
