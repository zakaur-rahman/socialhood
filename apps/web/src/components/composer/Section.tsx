import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** One block of the composer's left column (UX-SCR-13), titled for screen readers and the checklist. */
export function Section({
  id,
  title,
  aside,
  children,
  className,
  tabIndex,
}: {
  id: string;
  title: string;
  /** Shown beside the title: the format, a counter or a switch. */
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  /** -1 lets a checklist item move focus to the whole section. */
  tabIndex?: number;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      tabIndex={tabIndex}
      className={cn(
        // Focus (a checklist item moves it here) is the global outline.
        "scroll-mt-6 rounded-xl border border-line bg-panel p-4 md:p-5",
        className,
      )}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id={`${id}-title`} className="text-sm font-semibold">
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
