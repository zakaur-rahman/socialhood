"use client";

import { ExternalLink } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { PostDetail, SocialAccount } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { analysingText, formatCount, isAnalysing } from "@/lib/comments/format";
import { formatDayTime } from "@/lib/tz";

import { PostThumb } from "./PostThumb";
import { SentimentBar, SentimentLegend } from "./SentimentBar";

const LONG_CAPTION = 220;

/** FR-CMT-02: "Analysing 12,400 of 58,000 comments" with a bar, instead of numbers that look final. */
export function AnalysisProgress({ analysed, total }: { analysed: number; total: number }) {
  return (
    <div className="space-y-1.5" data-testid="analysis-progress">
      <p role="status" className="text-xs text-brand-fg">
        {analysingText({ analysed, total })}
      </p>
      <div
        role="progressbar"
        aria-label="Comments analysed"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={analysed}
        className="flex h-1 w-full overflow-hidden rounded-full bg-raised"
      >
        <span className="bg-brand-gradient-decor h-full" style={{ flexGrow: analysed, flexBasis: 0 }} />
        <span className="h-full" style={{ flexGrow: total - analysed, flexBasis: 0 }} />
      </div>
    </div>
  );
}

/**
 * UX-SCR-05 left column, first card: the post, its caption and counts (Instagram's likes and
 * comments at the last sync), and the comment sentiment split with spam (FR-CMT-04).
 */
export function PostPanel({
  post,
  account,
  slug,
  timeZone,
  now,
}: {
  post: PostDetail;
  account: SocialAccount | undefined;
  slug: string;
  timeZone: string;
  now: Date;
}) {
  const [expanded, setExpanded] = useState(false);
  const caption = post.caption?.trim() ?? "";
  const long = caption.length > LONG_CAPTION;
  const { stats } = post;
  const analysisOff = account?.ai_analysis_enabled === false;

  return (
    <section aria-label="Post" className="rounded-xl border border-line bg-panel p-4">
      <div className="flex gap-3 lg:flex-col">
        <PostThumb post={post} className="w-24 shrink-0 rounded-lg lg:w-full" />
        <div className="min-w-0 flex-1 space-y-2">
          {caption ? (
            <div>
              <p className={long && !expanded ? "line-clamp-4 text-sm whitespace-pre-line" : "text-sm whitespace-pre-line"}>
                {caption}
              </p>
              {long ? (
                <Button
                  variant="link"
                  size="xs"
                  // In line with the caption: no side padding.
                  className="mt-1 px-0"
                  onClick={() => setExpanded((value) => !value)}
                  aria-expanded={expanded}
                >
                  {expanded ? "Less" : "More"}
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-fg-secondary">No caption</p>
          )}
          <p className="text-xs text-fg-secondary">
            {account ? `${accountLabel(account)} · ` : ""}
            <time dateTime={post.posted_at}>{formatDayTime(post.posted_at, timeZone, now)}</time>
          </p>
          {post.permalink ? (
            <a
              href={post.permalink}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-brand-fg hover:underline pointer-coarse:min-h-10"
            >
              Open in Instagram <ExternalLink className="size-3" aria-hidden />
            </a>
          ) : null}
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-lg bg-field px-3 py-2">
          <dt className="text-xs text-fg-secondary">Likes</dt>
          <dd className="font-semibold tabular-nums">{post.like_count == null ? "—" : formatCount(post.like_count)}</dd>
        </div>
        <div className="rounded-lg bg-field px-3 py-2">
          <dt className="text-xs text-fg-secondary">Comments</dt>
          <dd className="font-semibold tabular-nums">{formatCount(stats.total)}</dd>
        </div>
      </dl>

      <div className="mt-4 space-y-2" aria-label="Comment sentiment" role="group">
        {analysisOff ? (
          <p className="text-xs text-fg-secondary">
            AI analysis is off for {account ? accountLabel(account) : "this account"}, so new comments aren&apos;t
            analysed.{" "}
            <Link href={`/w/${slug}/settings/connections` as Route} className="text-brand-fg hover:underline">
              Turn it on
            </Link>
          </p>
        ) : isAnalysing(stats) ? (
          <AnalysisProgress analysed={stats.analysed} total={stats.total} />
        ) : null}
        <SentimentBar positive={stats.positive} neutral={stats.neutral} negative={stats.negative} />
        <SentimentLegend positive={stats.positive} neutral={stats.neutral} negative={stats.negative} spam={stats.spam} />
      </div>
    </section>
  );
}
