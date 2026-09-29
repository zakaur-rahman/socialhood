import { MessageSquare } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import type { PostSummary } from "@/lib/api/types";
import { analysingText, formatCount, isAnalysing, mediaTypeLabel, plural } from "@/lib/comments/format";
import { formatDay } from "@/lib/tz";

import { PostThumb } from "./PostThumb";
import { SentimentBar } from "./SentimentBar";

export function postHref(slug: string, postId: string): Route {
  return `/w/${slug}/comments/${postId}` as Route;
}

/**
 * FR-CMT-03 / UX-SCR-05: square thumbnail, date, comment count, the 6 px sentiment bar and the spam
 * count. post.updated replaces the post in the cache, so the card follows new comments live (F-12).
 */
export function PostCard({
  post,
  slug,
  timeZone,
  now,
}: {
  post: PostSummary;
  slug: string;
  timeZone: string;
  now: Date;
}) {
  const { stats } = post;
  const caption = post.caption?.trim();
  const date = formatDay(post.posted_at, timeZone, now);
  return (
    <li data-testid="post-card" data-post-id={post.id}>
      <Link
        href={postHref(slug, post.id)}
        className="group block overflow-hidden rounded-xl border border-line bg-panel outline-none hover:border-line-strong focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <PostThumb post={post} className="border-b border-line" />
        <span className="sr-only">
          {caption ? caption.slice(0, 100) : "Post without a caption"}, {mediaTypeLabel(post.media_type)},{" "}
        </span>
        <div className="space-y-2 p-3">
          <div className="flex items-center justify-between gap-2 text-xs">
            <time dateTime={post.posted_at} className="truncate text-fg-secondary">
              {date}
            </time>
            <span className="inline-flex shrink-0 items-center gap-1 font-medium text-fg" data-testid="comment-count">
              <MessageSquare className="size-3.5 text-fg-secondary" aria-hidden />
              <span className="tabular-nums">{formatCount(stats.total)}</span>
              <span className="sr-only">{stats.total === 1 ? " comment" : " comments"}</span>
            </span>
          </div>
          <SentimentBar positive={stats.positive} neutral={stats.neutral} negative={stats.negative} />
          <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 text-xs text-fg-secondary">
            <span data-testid="spam-count">{stats.spam > 0 ? plural(stats.spam, "spam", "spam") : "No spam"}</span>
            {isAnalysing(stats) ? (
              <span className="text-brand-fg" title={analysingText(stats)}>
                Analysing {formatCount(stats.analysed)} of {formatCount(stats.total)}
              </span>
            ) : null}
          </div>
        </div>
      </Link>
    </li>
  );
}
