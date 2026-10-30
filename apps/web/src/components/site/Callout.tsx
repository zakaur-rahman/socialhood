import { Info, Lightbulb, MoveRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * A quiet aside in long text (C-159): a tip, a note, or "what this means for you". A sheet a tone
 * off the page with a small icon tile and a short title; no coloured edge. Server-rendered; the icon
 * is decorative, the title says what kind of aside it is. Styles: site.css, `.callout` (C-159 guides).
 */
export type CalloutTone = "tip" | "note" | "means";

const TONES: Record<CalloutTone, { icon: LucideIcon; title: string }> = {
  tip: { icon: Lightbulb, title: "Tip" },
  note: { icon: Info, title: "Note" },
  means: { icon: MoveRight, title: "What this means for you" },
};

export function Callout({ tone = "note", title, children }: { tone?: CalloutTone; title?: string; children: ReactNode }) {
  const { icon: Icon, title: fallback } = TONES[tone];
  return (
    <aside className={`callout callout-${tone}`} aria-label={title ?? fallback}>
      <span className="callout-ico" aria-hidden>
        <Icon size={18} strokeWidth={1.75} aria-hidden focusable="false" />
      </span>
      <div className="callout-b">
        <p className="callout-t">{title ?? fallback}</p>
        {children}
      </div>
    </aside>
  );
}
