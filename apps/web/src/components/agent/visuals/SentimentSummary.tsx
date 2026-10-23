import { useId } from "react";

import { SentimentBar, SentimentLegend } from "@/components/comments/SentimentBar";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { SentimentSummaryVisual } from "@/lib/api/types";
import { formatCount } from "@/lib/comments/format";

/**
 * GR-38: comment sentiment as one split bar with the counts, and the top topics when the run found
 * them (sentiment_distribution, comment_topics). Comments that aren't analysed yet are counted
 * apart, never folded into the bar. Topic labels come from customers' comments: drawn as text.
 */
export function SentimentSummary({ visual }: { visual: SentimentSummaryVisual }) {
  const titleId = useId();
  const analysed = visual.positive + visual.neutral + visual.negative;

  return (
    <Card asChild padding="standard" className="space-y-3">
      <section aria-labelledby={titleId} data-testid="visual-sentiment-summary">
        <CardHeader>
          <CardTitle id={titleId} className="text-sm">
            {visual.title}
          </CardTitle>
          <CardDescription>{visual.scope}</CardDescription>
        </CardHeader>
        {analysed === 0 ? (
          <p className="text-sm text-fg-secondary">
            {visual.total === 0 ? "No comments to show." : "No analysed comments yet."}
          </p>
        ) : (
          <div className="space-y-2">
            <SentimentBar positive={visual.positive} neutral={visual.neutral} negative={visual.negative} />
            <SentimentLegend
              positive={visual.positive}
              neutral={visual.neutral}
              negative={visual.negative}
              spam={visual.spam}
            />
          </div>
        )}
        {visual.not_analysed > 0 && analysed > 0 ? (
          <p className="text-xs text-fg-secondary" data-testid="sentiment-pending">
            {formatCount(visual.not_analysed)} of {formatCount(visual.total)} comments aren&apos;t analysed yet, so
            they aren&apos;t in the bar.
          </p>
        ) : null}
        {visual.topics.length > 0 ? (
          <div className="space-y-1">
            <h4 className="text-xs font-medium text-fg-secondary">Top topics</h4>
            <ul className="space-y-1" aria-label="Top topics">
              {visual.topics.map((topic) => (
                <li key={topic.label} className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate">{topic.label}</span>
                  <span className="shrink-0 text-xs text-fg-secondary tabular-nums">
                    {formatCount(topic.count)} {topic.count === 1 ? "comment" : "comments"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </Card>
  );
}
