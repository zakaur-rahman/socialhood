import type { Route } from "next";
import Link from "next/link";

import { PostThumb } from "@/components/comments/PostThumb";
import { SentimentBar } from "@/components/comments/SentimentBar";
import type { OverviewPost } from "@/lib/api/types";

import { formatCount, RANGE_LABEL, type OverviewRange } from "./format";

function caption(post: OverviewPost): string {
  const text = post.caption?.trim();
  return text ? text.split("\n")[0] : "Post without a caption";
}

/**
 * UX-SCR-01: the three posts with the most comments in the range, each with its comment
 * sentiment (the post's own split, as on the Comments page), linking to the post.
 */
export function TopPostsCard({ posts, range, slug }: { posts: OverviewPost[]; range: OverviewRange; slug: string }) {
  const days = RANGE_LABEL[range];
  return (
    <section aria-labelledby="home-top-posts" className="rounded-xl border border-line bg-panel p-4">
      <h2 id="home-top-posts" className="mb-3 text-base font-semibold">
        Most commented, {days}
      </h2>
      {posts.length === 0 ? (
        <p className="text-sm text-fg-secondary">No comments on your posts in the last {days}.</p>
      ) : (
        <ol className="space-y-1">
          {posts.map((post) => (
            <li key={post.id}>
              <Link
                href={`/w/${slug}/comments/${post.id}` as Route}
                data-testid="top-post"
                className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2 outline-none hover:bg-white/5 focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <PostThumb post={post} className="size-12 shrink-0 rounded-md" />
                <span className="min-w-0 flex-1 space-y-1.5">
                  <span className="block truncate text-sm">{caption(post)}</span>
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
    </section>
  );
}
