import { SentimentBar } from "@/components/comments/SentimentBar";
import type { SentimentSplit } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { formatCount, formatShare } from "./format";

const KEY = [
  { key: "positive", label: "Positive", dot: "bg-success" },
  { key: "neutral", label: "Neutral", dot: "bg-fg-secondary" },
  { key: "negative", label: "Negative", dot: "bg-danger" },
] as const;

function SplitRow({ title, noun, split, within }: { title: string; noun: string; split: SentimentSplit; within: string }) {
  const clean = split.positive + split.neutral + split.negative;
  return (
    <div data-testid={`sentiment-${noun}`} className="space-y-2">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-medium">{title}</h3>
        {split.total > 0 ? (
          <p className="text-xs text-fg-secondary tabular-nums">
            {formatCount(split.analysed)} of {formatCount(split.total)} analysed
          </p>
        ) : null}
      </div>
      {clean > 0 ? (
        <>
          <SentimentBar positive={split.positive} neutral={split.neutral} negative={split.negative} />
          <ul className="grid grid-cols-3 gap-x-3 gap-y-1 text-xs text-fg-secondary" aria-label={`${title} by sentiment`}>
            {KEY.map((item) => (
              <li key={item.key} className="inline-flex items-center gap-1.5">
                <span className={cn("size-2 shrink-0 rounded-full", item.dot)} aria-hidden />
                {item.label} <span className="text-fg tabular-nums">{formatShare(split[`${item.key}_pct`])}</span>
              </li>
            ))}
            {split.spam > 0 ? (
              <li className="inline-flex items-center gap-1.5">
                <span className="size-2 shrink-0 rounded-full bg-warning" aria-hidden />
                Spam <span className="text-fg tabular-nums">{formatCount(split.spam)}</span>
              </li>
            ) : null}
          </ul>
        </>
      ) : (
        <p className="text-xs text-fg-secondary">
          {split.total === 0 ? `No ${noun} in ${within}.` : "Not analysed yet."}
        </p>
      )}
    </div>
  );
}

/** UX-SCR-01: sentiment split bars for messages and comments over the range (FR-HOME-01). */
export function SentimentCard({
  messages,
  comments,
  period,
  within,
}: {
  messages: SentimentSplit;
  comments: SentimentSplit;
  /** "7 days" */
  period: string;
  /** "the last 7 days" */
  within: string;
}) {
  return (
    <section aria-labelledby="home-sentiment" className="flex flex-col gap-5 rounded-xl border border-line bg-panel p-4">
      <h2 id="home-sentiment" className="text-base font-semibold">
        Sentiment, {period}
      </h2>
      <SplitRow title="Messages" noun="messages" split={messages} within={within} />
      <SplitRow title="Comments" noun="comments" split={comments} within={within} />
    </section>
  );
}
