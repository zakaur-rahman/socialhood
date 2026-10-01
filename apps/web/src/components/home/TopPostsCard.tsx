import { ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { PostThumb } from "@/components/comments/PostThumb";
import { SentimentBar } from "@/components/comments/SentimentBar";
import type { OverviewEngagement, OverviewPost } from "@/lib/api/types";

import { formatCount } from "./format";

const rate = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

function caption(post: OverviewPost): string {
  const text = post.caption?.trim();
  return text ? text.split("\n")[0] : "Post without a caption";
}

/**
 * UX-SCR-01: the three posts with the most comments in the range, each with its comment
 * sentiment (the post's own split, as on the Comments page), linking to the post; View all goes
 * to Comments. The engagement rate shows only when the posts' metric snapshots in the range give
 * one: (likes + comments + shares + saves) ÷ reach, averaged over the posts that have it.
 */
export function TopPostsCard({
  posts,
  engagement,
  period,
  within,
  slug,
}: {
  posts: OverviewPost[];
  engagement: OverviewEngagement | null;
  period: string;
  within: string;
  slug: string;
}) {
  return (
    <section aria-labelledby="home-top-posts" className="flex min-w-0 flex-col rounded-xl border border-line bg-panel p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 id="home-top-posts" className="text-base font-semibold">
          Most commented, {period}
        </h2>
        <Link
          href={`/w/${slug}/comments` as Route}
          className="-my-2 inline-flex min-h-10 shrink-0 items-center gap-0.5 rounded-md text-sm font-medium text-brand-fg outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 md:min-h-8"
        >
          View all <ChevronRight className="size-4" aria-hidden />
        </Link>
      </div>
      {posts.length === 0 ? (
        <p className="text-sm text-fg-secondary">No comments on your posts in {within}.</p>
      ) : (
        <ol className="mb-3 space-y-1">
          {posts.map((post) => (
            <li key={post.id}>
              <Link
                href={`/w/${slug}/comments/${post.id}` as Route}
                data-testid="top-post"
                className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2 outline-none hover:bg-white/5 focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <PostThumb post={post} className="size-12 shrink-0 rounded-md" />
                <span className="min-w-0 flex-1 space-y-1.5">
                  <span className="block truncate text-sm font-medium">{caption(post)}</span>
                  <span className="flex items-center gap-3">
                    <span className="shrink-0 text-xs text-fg-secondary tabular-nums">
                      {formatCount(post.comments)} {post.comments === 1 ? "comment" : "comments"}
                    </span>
                    <SentimentBar
                      size="sm"
                      className="max-w-40"
                      positive={post.stats.positive}
                      neutral={post.stats.neutral}
                      negative={post.stats.negative}
                    />
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
      {engagement ? (
        <p data-testid="engagement" className="mt-auto border-t border-line-subtle pt-3 text-xs text-fg-secondary">
          Engagement rate <span className="font-medium text-fg tabular-nums">{rate.format(engagement.rate)}%</span>
          <span className="block">
            Average of {engagement.posts} {engagement.posts === 1 ? "post" : "posts"}: likes, comments, shares and saves
            per reach
          </span>
        </p>
      ) : null}
    </section>
  );
}
