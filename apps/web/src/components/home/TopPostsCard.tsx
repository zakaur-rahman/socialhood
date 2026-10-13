import { ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { PostThumb } from "@/components/comments/PostThumb";
import { SentimentBar } from "@/components/comments/SentimentBar";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
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
    <Card asChild className="flex flex-col">
      <section aria-labelledby="home-top-posts">
        <CardHeader className="mb-3">
          <CardTitle id="home-top-posts">Most commented, {period}</CardTitle>
          <CardAction>
            <Button asChild variant="link" size="sm">
              <Link href={`/w/${slug}/comments` as Route}>
                View all <ChevronRight aria-hidden />
              </Link>
            </Button>
          </CardAction>
        </CardHeader>
        {posts.length === 0 ? (
          <p className="text-sm text-fg-secondary">No comments on your posts in {within}.</p>
        ) : (
          <ol className="mb-3 space-y-1">
            {posts.map((post) => (
              <li key={post.id}>
                <Link
                  href={`/w/${slug}/comments/${post.id}` as Route}
                  data-testid="top-post"
                  className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-hover"
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
              Average of {engagement.posts} {engagement.posts === 1 ? "post" : "posts"}: likes, comments, shares and
              saves per reach
            </span>
          </p>
        ) : null}
      </section>
    </Card>
  );
}
