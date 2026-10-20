import type { ReactNode } from "react";

import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
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
    <Card asChild className={cn("scroll-mt-6", className)}>
      {/* Focus (a checklist item moves it here) is the global outline. */}
      <section id={id} aria-labelledby={`${id}-title`} tabIndex={tabIndex}>
        <CardHeader className="mb-3">
          <CardTitle id={`${id}-title`}>{title}</CardTitle>
          {aside ? <CardAction>{aside}</CardAction> : null}
        </CardHeader>
        {children}
      </section>
    </Card>
  );
}
