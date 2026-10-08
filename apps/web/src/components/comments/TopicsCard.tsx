import type { PostTopic } from "@/lib/api/types";
import { formatCount } from "@/lib/comments/format";
import { EYEBROW } from "@/styles/tokens";

import { SentimentBar } from "./SentimentBar";

/**
 * UX-SCR-05 topics (TR-AI-11): at most six labels, largest first, each with its comment count and
 * a small sentiment bar.
 */
export function TopicsCard({ topics, analysed }: { topics: PostTopic[]; analysed: number }) {
  return (
    <section aria-labelledby="post-topics-heading" className="space-y-3 rounded-xl border border-line bg-panel p-4">
      <h2 id="post-topics-heading" className={EYEBROW}>
        Topics
      </h2>
      {topics.length === 0 ? (
        <p className="text-sm text-fg-secondary">
          {analysed > 0
            ? "No topics yet. They're picked from the comments when the summary updates."
            : "Topics appear once comments are analysed."}
        </p>
      ) : (
        <ul className="space-y-3" aria-label="Topics">
          {topics.map((topic) => (
            <li key={topic.label} className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 break-words first-letter:uppercase">{topic.label}</span>
                <span className="shrink-0 text-xs text-fg-secondary tabular-nums">
                  {formatCount(topic.count)}
                  <span className="sr-only">{topic.count === 1 ? " comment" : " comments"}</span>
                </span>
              </div>
              <SentimentBar size="sm" positive={topic.positive} neutral={topic.neutral} negative={topic.negative} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
