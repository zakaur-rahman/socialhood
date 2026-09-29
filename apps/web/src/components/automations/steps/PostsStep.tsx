"use client";

import { Check, ImageOff, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { usePosts } from "@/lib/api/queries";
import type { AutomationDefinition, PostRef, PostScope } from "@/lib/api/types";
import { errorsFor, type FieldErrors } from "@/lib/automations/definition";
import { shortDate } from "@/lib/automations/format";
import { cn } from "@/lib/utils";

import { StepCard, type StepState } from "../StepCard";

const SCOPES: { value: PostScope; label: string; hint: string }[] = [
  { value: "all", label: "All posts", hint: "Comments on any of your posts, including new ones." },
  { value: "selected", label: "Selected posts", hint: "Only comments on the posts you pick below." },
  {
    value: "next_post",
    label: "Next post I publish",
    hint: "The next post you publish, from Social Hood or the Instagram app. It links itself when the post goes live.",
  },
];

const MEDIA_TYPE: Record<string, string> = {
  IMAGE: "Photo",
  VIDEO: "Video",
  REELS: "Reel",
  REEL: "Reel",
  CAROUSEL_ALBUM: "Carousel",
  CAROUSEL: "Carousel",
};

function mediaTypeLabel(type: string | null | undefined): string {
  if (!type) return "Post";
  return MEDIA_TYPE[type.toUpperCase()] ?? type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
}

/** A tile in the picker, from a synced post or one the automation already points at. */
type Tile = {
  key: string;
  mediaItemId: string | null;
  scheduledPostId: string | null;
  caption: string | null;
  thumbnail: string | null;
  type: string;
  date: string | null;
  scheduled: boolean;
};

function tileFromRef(ref: PostRef): Tile {
  return {
    key: ref.media_item_id ?? `scheduled-${ref.scheduled_post_id}`,
    mediaItemId: ref.media_item_id ?? null,
    scheduledPostId: ref.scheduled_post_id ?? null,
    caption: ref.caption ?? null,
    thumbnail: ref.thumbnail_url ?? null,
    type: mediaTypeLabel(ref.media_type),
    date: ref.posted_at ?? null,
    scheduled: !ref.media_item_id,
  };
}

/** UX-SCR-03 On these posts (comment triggers): all, chosen ones from a thumbnail grid, or the next post. */
export function PostsStep({
  wid,
  draft,
  change,
  errors,
  state,
  knownPosts,
  timeZone,
}: {
  wid: string;
  draft: AutomationDefinition;
  change: (patch: Partial<AutomationDefinition>) => void;
  errors: FieldErrors;
  state: StepState;
  /** The posts the saved automation points at (synced or scheduled). */
  knownPosts: PostRef[];
  timeZone: string;
}) {
  const anyComment = draft.trigger === "comment_any";
  const stepErrors = ["post_scope", "posts", "media_item_ids", "scheduled_post_ids"].flatMap((field) =>
    errorsFor(errors, field),
  );
  const hint = SCOPES.find((scope) => scope.value === draft.post_scope)?.hint;

  return (
    <StepCard id="posts" label="On these posts" state={state} errors={stepErrors}>
      <div className="space-y-3">
        <ToggleGroup
          aria-label="Which posts"
          aria-describedby="automation-scope-hint"
          value={draft.post_scope}
          onValueChange={(value) => change({ post_scope: value as PostScope })}
          className="flex-col sm:flex-row"
        >
          {SCOPES.map((scope) => (
            <ToggleGroupItem key={scope.value} value={scope.value} disabled={anyComment && scope.value === "all"}>
              {scope.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <p id="automation-scope-hint" className="text-xs text-fg-secondary">
          {anyComment && draft.post_scope === "all"
            ? "Any comment needs chosen posts or the next post, so it never answers every comment on the account."
            : hint}
        </p>
        {draft.post_scope === "selected" ? (
          draft.social_account_id ? (
            <PostPicker
              wid={wid}
              accountId={draft.social_account_id}
              selectedMedia={draft.media_item_ids ?? []}
              selectedScheduled={draft.scheduled_post_ids ?? []}
              knownPosts={knownPosts}
              timeZone={timeZone}
              onChange={(mediaIds, scheduledIds) => change({ media_item_ids: mediaIds, scheduled_post_ids: scheduledIds })}
            />
          ) : (
            <p className="text-sm text-fg-secondary">Choose the account in When to see its posts.</p>
          )
        ) : null}
      </div>
    </StepCard>
  );
}

function PostPicker({
  wid,
  accountId,
  selectedMedia,
  selectedScheduled,
  knownPosts,
  timeZone,
  onChange,
}: {
  wid: string;
  accountId: string;
  selectedMedia: string[];
  selectedScheduled: string[];
  knownPosts: PostRef[];
  timeZone: string;
  onChange: (mediaIds: string[], scheduledIds: string[]) => void;
}) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    if (text === q) return;
    const timer = window.setTimeout(() => setQ(text), 250);
    return () => window.clearTimeout(timer);
  }, [text, q]);

  const posts = usePosts(wid, accountId, q);
  const loaded = useMemo<Tile[]>(
    () =>
      posts.data?.pages.flatMap((page) =>
        page.items.map((post) => ({
          key: post.id,
          mediaItemId: post.id,
          scheduledPostId: null,
          caption: post.caption ?? null,
          thumbnail: post.thumbnail_url ?? post.media_url ?? null,
          type: mediaTypeLabel(post.media_type),
          date: post.posted_at,
          scheduled: false,
        })),
      ) ?? [],
    [posts.data],
  );
  // Chosen posts first, including scheduled ones and any the grid has not loaded.
  const tiles = useMemo(() => {
    const loadedIds = new Set(loaded.map((tile) => tile.mediaItemId));
    const pinned = knownPosts
      .map(tileFromRef)
      .filter((tile) =>
        tile.mediaItemId
          ? selectedMedia.includes(tile.mediaItemId) && !loadedIds.has(tile.mediaItemId)
          : tile.scheduledPostId !== null && selectedScheduled.includes(tile.scheduledPostId),
      );
    return q ? loaded : [...pinned, ...loaded];
  }, [knownPosts, loaded, q, selectedMedia, selectedScheduled]);

  const isSelected = (tile: Tile) =>
    tile.mediaItemId ? selectedMedia.includes(tile.mediaItemId) : selectedScheduled.includes(tile.scheduledPostId ?? "");
  const toggle = (tile: Tile) => {
    if (tile.mediaItemId) {
      const id = tile.mediaItemId;
      onChange(selectedMedia.includes(id) ? selectedMedia.filter((x) => x !== id) : [...selectedMedia, id], selectedScheduled);
    } else if (tile.scheduledPostId) {
      const id = tile.scheduledPostId;
      onChange(selectedMedia, selectedScheduled.filter((x) => x !== id));
    }
  };
  const count = selectedMedia.length + selectedScheduled.length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-48 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-secondary" aria-hidden />
          <label htmlFor="automation-post-search" className="sr-only">
            Search posts by caption
          </label>
          <input
            id="automation-post-search"
            type="search"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Search captions"
            autoComplete="off"
            className="h-9 w-full rounded-lg border border-line bg-field pr-3 pl-10 text-sm outline-none focus:bg-raised focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </div>
        <p className="text-xs text-fg-secondary tabular-nums" aria-live="polite">
          {count === 1 ? "1 post chosen" : `${count} posts chosen`}
        </p>
      </div>

      {posts.isPending ? (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5" aria-busy="true" aria-label="Loading posts">
          {Array.from({ length: 10 }, (_, i) => (
            <Skeleton key={i} className="aspect-square rounded-lg bg-raised" />
          ))}
        </div>
      ) : posts.isError ? (
        <p role="alert" className="text-sm text-danger-fg">
          Posts didn&apos;t load.{" "}
          <button type="button" className="underline underline-offset-4" onClick={() => void posts.refetch()}>
            Try again
          </button>
        </p>
      ) : tiles.length === 0 ? (
        <p className="text-sm text-fg-secondary">
          {q ? `No posts match "${q}".` : "No posts yet. They appear here once the account has published."}
        </p>
      ) : (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5" aria-label="Posts">
          {tiles.map((tile) => {
            const selected = isSelected(tile);
            const caption = tile.caption?.trim();
            const date = tile.date ? shortDate(tile.date, timeZone) : tile.scheduled ? "Scheduled" : "";
            return (
              <li key={tile.key}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => toggle(tile)}
                  disabled={tile.scheduled && !selected}
                  className={cn(
                    "group relative grid aspect-square w-full place-items-center overflow-hidden rounded-lg border-2 bg-raised outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                    selected ? "border-brand" : "border-transparent opacity-80 hover:opacity-100",
                  )}
                >
                  {tile.thumbnail ? (
                    // eslint-disable-next-line @next/next/no-img-element -- Instagram CDN thumbnails of any size
                    <img src={tile.thumbnail} alt="" loading="lazy" className="size-full object-cover" />
                  ) : (
                    <ImageOff className="size-5 text-fg-secondary" aria-hidden />
                  )}
                  <span className="sr-only">
                    {caption ? caption.slice(0, 80) : "Post without a caption"}, {tile.type}
                    {date ? `, ${date}` : ""}
                  </span>
                  <span
                    aria-hidden
                    className="absolute inset-x-0 bottom-0 flex justify-between gap-1 bg-canvas/70 px-1.5 py-0.5 text-[10px] text-fg"
                  >
                    <span>{tile.scheduled ? "Scheduled" : tile.type}</span>
                    <span>{tile.date ? shortDate(tile.date, timeZone) : ""}</span>
                  </span>
                  {selected ? (
                    <span aria-hidden className="absolute top-1 right-1 grid size-5 place-items-center rounded-full bg-brand text-white">
                      <Check className="size-3.5" />
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {posts.hasNextPage ? (
        <Button variant="secondary" size="sm" onClick={() => void posts.fetchNextPage()} disabled={posts.isFetchingNextPage}>
          Show more posts
        </Button>
      ) : null}
    </div>
  );
}
