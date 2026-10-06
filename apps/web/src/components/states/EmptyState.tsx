import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Props = {
  title: string;
  body?: string;
  /** One action. In a compact state, a `size="sm"` Button (40 px on coarse pointers). */
  action?: ReactNode;
  icon?: ReactNode;
  /**
   * `default`: centred, for a page or a pane. `compact`: left-aligned 14 px text, for a block
   * inside a card, a list or a panel, where a centred state would be too loud (DESIGN_SYSTEM §8.2).
   */
  size?: "default" | "compact";
  className?: string;
};

/** A calm empty state with at most one action (§4.7). */
export function EmptyState({ title, body, action, icon, size = "default", className }: Props) {
  if (size === "compact") {
    return (
      <div data-size="compact" className={cn("flex items-start gap-2 text-left text-sm", className)}>
        {icon ? (
          <span className="flex h-5 shrink-0 items-center text-fg-secondary [&_svg]:size-4" aria-hidden>
            {icon}
          </span>
        ) : null}
        <div className="flex min-w-0 flex-col items-start gap-1">
          <p className="font-semibold">{title}</p>
          {body ? <p className="text-fg-secondary">{body}</p> : null}
          {action ? <div className="mt-1">{action}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <div
      data-size="default"
      className={cn("flex flex-col items-center justify-center gap-2 px-6 py-10 text-center", className)}
    >
      {icon ? <div className="mb-1 text-fg-secondary">{icon}</div> : null}
      <p className="text-base font-semibold">{title}</p>
      {body ? <p className="max-w-sm text-sm text-fg-secondary">{body}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
