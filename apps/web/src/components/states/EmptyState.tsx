import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Props = {
  title: string;
  body?: string;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
};

/** A calm empty state with at most one action (§4.7). */
export function EmptyState({ title, body, action, icon, className }: Props) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-6 py-10 text-center", className)}>
      {icon ? <div className="mb-1 text-fg-secondary">{icon}</div> : null}
      <p className="text-base font-semibold">{title}</p>
      {body ? <p className="max-w-sm text-sm text-fg-secondary">{body}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
