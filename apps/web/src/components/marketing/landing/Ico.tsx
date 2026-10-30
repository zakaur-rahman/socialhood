import type { LucideIcon } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

/**
 * A card's icon (C-157 motion, the owner's ask): a lucide icon at 20 px and one stroke weight, in a
 * small rounded tile on the surface token (site.css `.ico`). Server-rendered SVG, hidden from
 * assistive tech: the title next to it says the same thing. Ink-3 at rest, ink when its card is
 * hovered; iris only where the card is an AI moment (`.ico-ai`). `children` replaces the icon with a
 * mark of its own (a channel's glyph in its colour, in the connections).
 */
export function Ico({ icon: Icon, className, style, children }: { icon?: LucideIcon; className?: string; style?: CSSProperties; children?: ReactNode }) {
  return (
    <span className={className ? `ico ${className}` : "ico"} style={style} aria-hidden>
      {Icon ? <Icon size={20} strokeWidth={1.75} aria-hidden focusable="false" /> : children}
    </span>
  );
}
