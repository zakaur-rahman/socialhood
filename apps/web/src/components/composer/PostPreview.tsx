"use client";

import {
  Bookmark,
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  GalleryHorizontal,
  Heart,
  ImageIcon,
  MessageCircle,
  MoreHorizontal,
  Music2,
  Send,
} from "lucide-react";
import { Fragment, useState, type ReactNode } from "react";

import { PostThumb } from "@/components/comments/PostThumb";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldControl, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePosts } from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { MAX_RATIO, MIN_RATIO, ratioOf, type AssetInfo } from "@/lib/publishing/rules";
import type { PostFormat } from "@/lib/publishing/types";
import type { AccountColor } from "@/lib/schedule/format";
import { cn } from "@/lib/utils";

import { AccountPicture } from "./AccountPicker";

const CAPTION_PREVIEW_CHARS = 125;
const GRID_RECENT = 8;

type Tab = "feed" | "reel" | "grid";

// Strings, not literals: \p{…} is ES2018 syntax, above the tsconfig target.
const TAG_SPLIT = new RegExp("([#@][\\p{L}\\p{M}\\p{N}_.]+)", "u");
const TAG_ONLY = new RegExp("^[#@][\\p{L}\\p{M}\\p{N}_.]+$", "u");

/** Hashtags and mentions in the brand-fg link colour, as Instagram shows them. */
function RichCaption({ text }: { text: string }) {
  const parts = text.split(TAG_SPLIT);
  return (
    <>
      {parts.map((part, index) =>
        TAG_ONLY.test(part) ? (
          <span key={index} className="text-brand-fg">
            {part}
          </span>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function Media({ asset, className }: { asset: AssetInfo; className?: string }) {
  if (asset.resource_type === "video") {
    return (
      <video
        src={asset.url}
        poster={asset.thumbnail_url ?? undefined}
        muted
        playsInline
        preload="metadata"
        aria-label="Video"
        className={cn("size-full object-cover", className)}
      />
    );
  }
  // eslint-disable-next-line @next/next/no-img-element -- uploaded media of any size
  return <img src={asset.thumbnail_url ?? asset.url} alt="" className={cn("size-full object-cover", className)} />;
}

function NoMedia({ children = "Add a photo or video to see the preview." }: { children?: ReactNode }) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-2 p-6 text-center text-sm text-fg-secondary">
      <ImageIcon className="size-6" aria-hidden />
      {children}
    </div>
  );
}

function AccountHeader({ account, identity, subtitle }: { account: SocialAccount | null; identity?: AccountColor; subtitle?: string }) {
  const name = account?.username ?? account?.display_name ?? "your.account";
  return (
    <div className="flex items-center gap-2.5 px-3 py-2.5">
      <AccountPicture account={account} identity={identity} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{name}</p>
        {subtitle ? <p className="truncate text-xs text-fg-secondary">{subtitle}</p> : null}
      </div>
      <MoreHorizontal className="size-4 text-fg-secondary" aria-hidden />
    </div>
  );
}

/**
 * FR-PUB-03, UX-SCR-13: Feed, Reel and profile-grid previews with the real account name and
 * picture. With captions per account, a switcher shows each account's version.
 */
export function PostPreview({
  wid,
  accounts,
  identities,
  captionFor,
  captionsDiffer,
  assets,
  format,
  firstComment,
}: {
  wid: string;
  /** The post's accounts, in order; the first leads the preview. */
  accounts: SocialAccount[];
  /** Each account's identity colour, as Schedule shows it. */
  identities?: Map<string, AccountColor>;
  captionFor: (accountId: string | null) => string;
  captionsDiffer: boolean;
  assets: AssetInfo[];
  format: PostFormat | null;
  firstComment: string | null;
}) {
  const [tab, setTab] = useState<Tab>(format === "reel" ? "reel" : "feed");
  const [chosenId, setChosenId] = useState<string | null>(null);
  const account = accounts.find((item) => item.id === chosenId) ?? accounts[0] ?? null;
  const identity = account ? identities?.get(account.id) : undefined;
  const caption = captionFor(account?.id ?? null);

  return (
    <Card asChild>
     <section aria-labelledby="composer-preview-title">
      <CardHeader className="mb-3">
        <CardTitle id="composer-preview-title">Preview</CardTitle>
        {captionsDiffer && accounts.length > 1 ? (
          <CardAction>
           <Field id="preview-account" orientation="horizontal" density="compact" className="w-auto">
            <FieldLabel>Account</FieldLabel>
            <Select value={account?.id ?? ""} onValueChange={setChosenId}>
              <FieldControl>
                <SelectTrigger size="lg">
                  <SelectValue />
                </SelectTrigger>
              </FieldControl>
              <SelectContent>
                {accounts.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    @{item.username ?? item.display_name ?? "account"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
           </Field>
          </CardAction>
        ) : null}
      </CardHeader>
      <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
        <TabsList aria-label="Preview">
          <TabsTrigger value="feed">Feed</TabsTrigger>
          <TabsTrigger value="reel">Reel</TabsTrigger>
          <TabsTrigger value="grid">Grid</TabsTrigger>
        </TabsList>
        <TabsContent value="feed">
          <FeedPreview account={account} identity={identity} caption={caption} assets={assets} firstComment={firstComment} />
        </TabsContent>
        <TabsContent value="reel">
          {format === "reel" ? (
            <ReelPreview account={account} identity={identity} caption={caption} asset={assets[0]} />
          ) : (
            <div className="aspect-[9/16] max-h-[420px] w-full rounded-xl border border-line bg-canvas">
              <NoMedia>A Reel preview shows when the post is a single video.</NoMedia>
            </div>
          )}
        </TabsContent>
        <TabsContent value="grid">
          <GridPreview wid={wid} account={account} identity={identity} assets={assets} format={format} />
        </TabsContent>
      </Tabs>
     </section>
    </Card>
  );
}

function FeedPreview({
  account,
  identity,
  caption,
  assets,
  firstComment,
}: {
  account: SocialAccount | null;
  identity?: AccountColor;
  caption: string;
  assets: AssetInfo[];
  firstComment: string | null;
}) {
  const [slide, setSlide] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const index = Math.min(slide, Math.max(0, assets.length - 1));
  const current = assets[index];
  // Instagram crops every feed item to the first one's shape, within 4:5 to 1.91:1.
  const firstRatio = assets[0] ? (ratioOf(assets[0]) ?? 1) : 1;
  const ratio = assets[0]?.resource_type === "video" && assets.length === 1 ? MIN_RATIO : Math.min(Math.max(firstRatio, MIN_RATIO), MAX_RATIO);
  const name = account?.username ?? account?.display_name ?? "your.account";
  const chars = [...caption];
  const long = chars.length > CAPTION_PREVIEW_CHARS;
  const shown = long && !expanded ? `${chars.slice(0, CAPTION_PREVIEW_CHARS).join("").trimEnd()}…` : caption;

  return (
    <article aria-label="Feed preview" className="overflow-hidden rounded-xl border border-line bg-canvas">
      <AccountHeader account={account} identity={identity} />
      <div className="relative w-full bg-field" style={{ aspectRatio: `${ratio}` }}>
        {current ? <Media asset={current} /> : <NoMedia />}
        {assets.length > 1 ? (
          <>
            <span className="absolute top-2 right-2 rounded-full bg-media-scrim/70 px-2 py-0.5 text-xs tabular-nums" data-testid="carousel-counter">
              {index + 1}/{assets.length}
            </span>
            {/* Instagram's white arrows on the photo: 32 px, 40 px on coarse pointers. */}
            {index > 0 ? (
              <button
                type="button"
                aria-label="Previous item"
                onClick={() => setSlide(index - 1)}
                className="absolute top-1/2 left-2 grid size-8 -translate-y-1/2 place-items-center rounded-full bg-fg/80 text-canvas hover:bg-fg pointer-coarse:size-10"
              >
                <ChevronLeft className="size-4" aria-hidden />
              </button>
            ) : null}
            {index < assets.length - 1 ? (
              <button
                type="button"
                aria-label="Next item"
                onClick={() => setSlide(index + 1)}
                className="absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center rounded-full bg-fg/80 text-canvas hover:bg-fg pointer-coarse:size-10"
              >
                <ChevronRight className="size-4" aria-hidden />
              </button>
            ) : null}
          </>
        ) : null}
      </div>
      <div className="flex items-center gap-3 px-3 pt-2.5 text-fg" aria-hidden>
        <Heart className="size-5" />
        <MessageCircle className="size-5" />
        <Send className="size-5" />
        {assets.length > 1 ? (
          <span className="mx-auto flex gap-1">
            {assets.map((asset, dot) => (
              <span key={asset.id} className={cn("size-1.5 rounded-full", dot === index ? "bg-brand" : "bg-fg-disabled")} />
            ))}
          </span>
        ) : (
          <span className="flex-1" />
        )}
        <Bookmark className="size-5" />
      </div>
      <div className="space-y-1 px-3 pt-2 pb-3 text-sm">
        {caption.trim() ? (
          <p className="break-words whitespace-pre-line" data-testid="preview-caption">
            <span className="font-semibold">{name}</span> <RichCaption text={shown} />
            {long ? (
              <button type="button" onClick={() => setExpanded(!expanded)} className="ml-1 text-fg-secondary hover:text-fg">
                {expanded ? "less" : "more"}
              </button>
            ) : null}
          </p>
        ) : (
          <p className="text-fg-secondary">Your caption shows here.</p>
        )}
        {firstComment?.trim() ? (
          <p className="line-clamp-2 break-words text-fg-secondary" data-testid="preview-first-comment">
            <span className="font-semibold text-fg">{name}</span> <RichCaption text={firstComment} />
          </p>
        ) : null}
      </div>
    </article>
  );
}

function ReelPreview({
  account,
  identity,
  caption,
  asset,
}: {
  account: SocialAccount | null;
  identity?: AccountColor;
  caption: string;
  asset: AssetInfo | undefined;
}) {
  const name = account?.username ?? account?.display_name ?? "your.account";
  return (
    <article aria-label="Reel preview" className="relative mx-auto aspect-[9/16] max-h-[520px] overflow-hidden rounded-xl border border-line bg-canvas">
      {asset ? <Media asset={asset} /> : <NoMedia />}
      <div className="absolute inset-x-0 bottom-0 space-y-2 bg-linear-to-t from-canvas/90 to-transparent p-3 pr-12">
        <div className="flex items-center gap-2">
          <AccountPicture account={account} identity={identity} size={24} />
          <span className="truncate text-sm font-semibold">{name}</span>
        </div>
        {caption.trim() ? (
          <p className="line-clamp-2 text-sm break-words" data-testid="reel-caption">
            <RichCaption text={caption} />
          </p>
        ) : null}
        <p className="flex items-center gap-1 text-xs text-fg-secondary">
          <Music2 className="size-3" aria-hidden /> Original audio
        </p>
      </div>
      <div className="absolute right-2 bottom-4 flex flex-col items-center gap-4 text-fg" aria-hidden>
        <Heart className="size-5" />
        <MessageCircle className="size-5" />
        <Send className="size-5" />
        <MoreHorizontal className="size-5" />
      </div>
    </article>
  );
}

const FORMAT_ICON = { carousel: GalleryHorizontal, reel: Clapperboard } as const;

function GridPreview({
  wid,
  account,
  identity,
  assets,
  format,
}: {
  wid: string;
  account: SocialAccount | null;
  identity?: AccountColor;
  assets: AssetInfo[];
  format: PostFormat | null;
}) {
  const posts = usePosts(wid, account?.id ?? null, "");
  const recent = (posts.data?.pages[0]?.items ?? []).slice(0, GRID_RECENT);
  const first = assets[0];
  const Icon = format === "carousel" || format === "reel" ? FORMAT_ICON[format] : null;
  return (
    <article aria-label="Grid preview" className="overflow-hidden rounded-xl border border-line bg-canvas">
      <AccountHeader account={account} identity={identity} subtitle="Profile grid" />
      <ul className="grid grid-cols-3 gap-0.5" aria-label="Profile grid">
        <li className="relative aspect-square bg-field ring-2 ring-brand ring-inset" aria-label="This post">
          {first ? (
            first.resource_type === "video" && !first.thumbnail_url ? (
              <video src={first.url} muted playsInline preload="metadata" aria-hidden className="size-full object-cover" />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element -- uploaded media of any size
              <img src={first.thumbnail_url ?? first.url} alt="" className="size-full object-cover" />
            )
          ) : (
            <span className="grid size-full place-items-center text-xs text-fg-secondary">New post</span>
          )}
          {Icon ? (
            <span className="absolute top-1.5 right-1.5 grid size-6 place-items-center rounded-md bg-media-scrim/70" aria-hidden>
              <Icon className="size-3.5" />
            </span>
          ) : null}
          <Badge tone="count" shape="tag" className="absolute bottom-1.5 left-1.5">
            New
          </Badge>
        </li>
        {account && posts.isPending
          ? Array.from({ length: GRID_RECENT }, (_, index) => (
              <li key={index} aria-hidden>
                <Skeleton className="aspect-square rounded-none" />
              </li>
            ))
          : recent.map((post) => (
              <li key={post.id}>
                <PostThumb post={post} />
              </li>
            ))}
      </ul>
      {account && !posts.isPending && recent.length === 0 ? (
        <p className="px-3 py-3 text-xs text-fg-secondary">Posts from {`@${account.username ?? "this account"}`} show here once they sync.</p>
      ) : null}
    </article>
  );
}
