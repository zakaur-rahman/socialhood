import { formatCount, sentimentLabel } from "@/lib/comments/format";
import { cn } from "@/lib/utils";

const SEGMENTS = [
  { key: "positive", className: "bg-success" },
  { key: "neutral", className: "bg-fg-secondary" },
  { key: "negative", className: "bg-danger" },
] as const;

/**
 * UX-SCR-05: positive, neutral and negative as one bar (6 px on cards, 4 px beside topics). Each
 * segment grows by its count, so the widths are the API's counts without any arithmetic here.
 */
export function SentimentBar({
  positive,
  neutral,
  negative,
  size = "md",
  className,
}: {
  positive: number;
  neutral: number;
  negative: number;
  size?: "md" | "sm";
  className?: string;
}) {
  const counts = { positive, neutral, negative };
  const empty = positive + neutral + negative === 0;
  return (
    <div
      role="img"
      aria-label={sentimentLabel(counts)}
      data-testid="sentiment-bar"
      className={cn(
        "flex w-full gap-px overflow-hidden rounded-full bg-raised",
        size === "md" ? "h-1.5" : "h-1",
        className,
      )}
    >
      {empty
        ? null
        : SEGMENTS.map((segment) =>
            counts[segment.key] > 0 ? (
              <span
                key={segment.key}
                data-sentiment={segment.key}
                className={cn("h-full", segment.className)}
                style={{ flexGrow: counts[segment.key], flexBasis: 0 }}
              />
            ) : null,
          )}
    </div>
  );
}

/** The bar's key: a dot, the label and the count for each sentiment, and spam. */
export function SentimentLegend({
  positive,
  neutral,
  negative,
  spam,
}: {
  positive: number;
  neutral: number;
  negative: number;
  spam?: number;
}) {
  const items = [
    { label: "Positive", value: positive, dot: "bg-success" },
    { label: "Neutral", value: neutral, dot: "bg-fg-secondary" },
    { label: "Negative", value: negative, dot: "bg-danger" },
    ...(spam !== undefined ? [{ label: "Spam", value: spam, dot: "bg-warning" }] : []),
  ];
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-fg-secondary" aria-label="Comment counts">
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-1.5">
          <span className={cn("size-2 rounded-full", item.dot)} aria-hidden />
          {item.label} <span className="text-fg tabular-nums">{formatCount(item.value)}</span>
        </li>
      ))}
    </ul>
  );
}
