import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Ico } from "@/components/marketing/landing/Ico";

/**
 * A quiet aside in running text (C-159): an icon tile beside an optional title and the text. For a
 * note, a tip, or details to act on (contact, grievances). A tone step on the paper, no coloured
 * edge; iris only on an AI moment (`ai`). Server-rendered, no script. Styles: site.css `.callout`.
 */
export function Callout({
  icon,
  title,
  ai = false,
  className,
  children,
}: {
  icon: LucideIcon;
  title?: ReactNode;
  ai?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={className ? `callout ${className}` : "callout"}>
      <Ico icon={icon} className={ai ? "ico-ai" : undefined} />
      <div className="callout-b">
        {title ? <p className="callout-t">{title}</p> : null}
        {children}
      </div>
    </div>
  );
}
