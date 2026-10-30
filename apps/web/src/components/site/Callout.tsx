import { Info, Lightbulb, MoveRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * A quiet aside in running text (C-159), shared by the guides and the legal and information pages:
 * an icon tile beside a short title and the text, no coloured edge. Server-rendered, no script.
 *
 * - `tone` sets the look, the default icon and the default title: `note` and `tip` sit on a sheet with
 *   a hairline, `means` ("What this means for you") on a tone step with the tile in ink, and `info`
 *   on a tone step with a larger quiet tile and no title unless one is given (details to act on).
 * - `icon` replaces the tone's icon; `title` replaces its title; `ai` puts the icon in iris, for an
 *   AI moment only.
 *
 * The aside is named by its title (or its kind), so a screen reader says what kind of aside it is;
 * the icon is decorative. Styles: site.css, `.callout` (C-159 shared).
 */
export type CalloutTone = "note" | "tip" | "means" | "info";

const TONES: Record<CalloutTone, { icon: LucideIcon; title?: string; label: string }> = {
  note: { icon: Info, title: "Note", label: "Note" },
  tip: { icon: Lightbulb, title: "Tip", label: "Tip" },
  means: { icon: MoveRight, title: "What this means for you", label: "What this means for you" },
  info: { icon: Info, label: "Note" },
};

export function Callout({
  tone = "note",
  icon,
  title,
  ai = false,
  className,
  children,
}: {
  tone?: CalloutTone;
  icon?: LucideIcon;
  title?: string;
  ai?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const kind = TONES[tone];
  const Icon = icon ?? kind.icon;
  const shown = title ?? kind.title;
  const classes = ["callout", `callout-${tone}`, ai ? "callout-ai" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <aside className={classes} aria-label={shown ?? kind.label}>
      <span className="callout-ico" aria-hidden>
        <Icon size={18} strokeWidth={1.75} aria-hidden focusable="false" />
      </span>
      <div className="callout-b">
        {shown ? <p className="callout-t">{shown}</p> : null}
        {children}
      </div>
    </aside>
  );
}
