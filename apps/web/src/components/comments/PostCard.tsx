import { MessageSquare } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { PostSummary } from "@/lib/api/types";
import { analysingText, formatCount, isAnalysing, mediaTypeLabel, plural } from "@/lib/comments/format";
import { formatDay } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { PostThumb } from "./PostThumb";
import { SentimentBar } from "./SentimentBar";

export function postHref(slug: string, postId: string, filter?: "needs_reply"): Route {
  return `/w/${slug}/comments/${postId}${filter ? `?filter=${filter}` : ""}` as Route;
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
  const waiting = post.needs_reply_count ?? 0;
  // The caption's first non-empty line: its hook, enough to tell the cards apart (UI-ISS-112).
  const firstLine = post.caption
    ?.split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean);
  const date = formatDay(post.posted_at, timeZone, now);
  return (
    <li data-testid="post-card" data-post-id={post.id}>
      <Card asChild className="block overflow-hidden p-0 hover:border-line-strong">
        <Link href={postHref(slug, post.id, waiting > 0 ? "needs_reply" : undefined)}>
          <PostThumb post={post} className="border-b border-line" />
          <div className="space-y-2 p-3">
            <p
              className={cn("truncate text-sm font-medium", !firstLine && "text-fg-secondary")}
              data-testid="post-caption"
            >
              <span className="sr-only">{mediaTypeLabel(post.media_type)}: </span>
              {firstLine || "No caption"}
            </p>
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
            {waiting > 0 ? (
              <Badge tone="warning" size="md" data-testid="needs-reply-count">
                {formatCount(waiting)} {waiting === 1 ? "needs" : "need"} a reply
              </Badge>
            ) : null}
            <SentimentBar positive={stats.positive} neutral={stats.neutral} negative={stats.negative} />
            {/* Only what's worth a line: spam above 0 (not "No spam" on every card), or the analysis. */}
            {stats.spam > 0 || isAnalysing(stats) ? (
              <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 text-xs text-fg-secondary">
                {stats.spam > 0 ? <span data-testid="spam-count">{plural(stats.spam, "spam", "spam")}</span> : null}
                {isAnalysing(stats) ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="text-brand-fg">
                        Analysing {formatCount(stats.analysed)} of {formatCount(stats.total)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>{analysingText(stats)}</TooltipContent>
                  </Tooltip>
                ) : null}
              </div>
            ) : null}
          </div>
        </Link>
      </Card>
    </li>
  );
}
