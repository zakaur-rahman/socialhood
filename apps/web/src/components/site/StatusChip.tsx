import { Check, Clock, Hourglass, type LucideIcon, Minus, SearchX } from "lucide-react";

import { STATUS_LABEL, type Status } from "@/lib/marketing/gtm-pages";

const CHIP: Record<Status, { icon: LucideIcon; tone: string }> = {
  yes: { icon: Check, tone: "t-ok" },
  soon: { icon: Clock, tone: "t-plain" },
  approval: { icon: Hourglass, tone: "t-need" },
  no: { icon: Minus, tone: "t-plain" },
  "not-found": { icon: SearchX, tone: "t-plain" },
};

/**
 * A status as a chip with its icon (C-159): yes, coming soon, with Meta's approval, not offered,
 * not found. The words are STATUS_LABEL's, unchanged; the icon is decoration, so the label alone is
 * what a screen reader hears. Shared by the comparison tables and the audience pages' feature cards.
 */
export function StatusChip({ status, className }: { status: Status; className?: string }) {
  const { icon: Icon, tone } = CHIP[status];
  return (
    <span className={`tag chip ${tone}${className ? ` ${className}` : ""}`} data-status={status}>
      <Icon size={13} strokeWidth={2.25} aria-hidden focusable="false" />
      {STATUS_LABEL[status]}
    </span>
  );
}

/**
 * A plain value as a chip (C-159), for the pricing page's flag cells: "Included" and "Not included"
 * get the yes / not-offered look; any other value is returned as text.
 */
export function ValueChip({ value }: { value: string }) {
  if (value === "Included") return <span className="tag chip t-ok"><Check size={13} strokeWidth={2.25} aria-hidden focusable="false" />{value}</span>;
  if (value === "Not included") return <span className="tag chip t-plain"><Minus size={13} strokeWidth={2.25} aria-hidden focusable="false" />{value}</span>;
  return <>{value}</>;
}
