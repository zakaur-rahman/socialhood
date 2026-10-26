"use client";

import { ExternalLink } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ContactAvatar } from "@/components/inbox/ContactAvatar";
import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useSocialAccounts, useStoryMentions } from "@/lib/api/queries";
import type { StoryMention } from "@/lib/api/types";
import { accountLabel, instagramAccounts } from "@/lib/automations/accounts";
import { formatCount } from "@/lib/comments/format";
import { emptyStates } from "@/lib/copy";
import { formatDayTime } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

const ALL = "all";

function who(mention: StoryMention): string {
  const contact = mention.contact;
  if (!contact) return "Someone";
  return contact.display_name?.trim() || (contact.username ? `@${contact.username}` : "Someone");
}

/**
 * GR-07: who mentioned the account in their story, and when. The story's link is Instagram's own
 * address and only works while the story is live (24 hours); after that the row says it expired.
 * Amplychat never copies the story.
 */
export function MentionsPage() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const now = useNow();
  const [accountId, setAccountId] = useState<string | null>(null);
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => instagramAccounts(allAccounts.data ?? []), [allAccounts.data]);
  const mentions = useStoryMentions(wid, accountId);
  const items = mentions.data?.pages.flatMap((page) => page.items) ?? [];
  const recent = mentions.data?.pages[0]?.total_7d ?? 0;

  let content;
  if (mentions.isPending) {
    content = (
      <Card>
        <ul aria-busy="true" aria-label="Loading mentions" className="divide-y divide-line-subtle">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="flex items-center gap-3 px-4 py-3">
              <Skeleton className="size-8 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </li>
          ))}
        </ul>
      </Card>
    );
  } else if (mentions.isError) {
    content = <ErrorState error={mentions.error} onRetry={() => void mentions.refetch()} />;
  } else if (items.length === 0) {
    content = (
      <Card>
        <EmptyState size="compact" {...emptyStates.storyMentions} />
      </Card>
    );
  } else {
    content = (
      <div className="space-y-4">
        <p className="text-sm text-fg-secondary" data-testid="mentions-total">
          {recent === 1 ? "1 mention in the last 7 days." : `${formatCount(recent)} mentions in the last 7 days.`}
        </p>
        <Card className="overflow-hidden p-0">
          <ul aria-label="Story mentions" className="divide-y divide-line-subtle">
            {items.map((mention) => (
              <MentionRow key={mention.id} mention={mention} slug={workspace.slug} timeZone={workspace.timezone} now={now} />
            ))}
          </ul>
        </Card>
        {mentions.hasNextPage ? (
          <div className="flex justify-center">
            <Button
              variant="secondary"
              onClick={() => void mentions.fetchNextPage()}
              disabled={mentions.isFetchingNextPage}
            >
              {mentions.isFetchingNextPage ? "Loading…" : "Show older mentions"}
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <PageFrame
      title="Story mentions"
      back={{ href: `/w/${workspace.slug}/comments` as Route, label: "Comments" }}
      actions={
        accounts.length > 1 ? (
          <Select value={accountId ?? ALL} onValueChange={(value) => setAccountId(value === ALL ? null : value)}>
            <SelectTrigger aria-label="Account" size="lg" className="max-w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All accounts</SelectItem>
              {accounts.map((account) => (
                <SelectItem key={account.id} value={account.id}>
                  {accountLabel(account)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null
      }
    >
      {content}
    </PageFrame>
  );
}

function MentionRow({
  mention,
  slug,
  timeZone,
  now,
}: {
  mention: StoryMention;
  slug: string;
  timeZone: string;
  now: Date;
}) {
  const name = who(mention);
  const username = mention.contact?.username;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3" data-testid="mention-row">
      <ContactAvatar
        id={mention.contact?.id ?? mention.id}
        name={name}
        pictureUrl={mention.contact?.profile_picture_url}
        size={32}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{name}</p>
        <p className="text-xs text-fg-secondary">
          {username && name !== `@${username}` ? `@${username} · ` : ""}
          <time dateTime={mention.mentioned_at}>{formatDayTime(mention.mentioned_at, timeZone, now)}</time>
        </p>
      </div>
      <div className="flex items-center gap-3 text-sm">
        {mention.link_url ? (
          <a
            href={mention.link_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 text-brand-fg underline underline-offset-4"
          >
            View story
            <ExternalLink className="size-3.5" aria-hidden />
          </a>
        ) : (
          <span className="text-fg-secondary">Story expired</span>
        )}
        {mention.conversation_id ? (
          <Link
            href={`/w/${slug}/inbox/${mention.conversation_id}` as Route}
            className="text-brand-fg underline underline-offset-4"
          >
            Open conversation
          </Link>
        ) : null}
      </div>
    </li>
  );
}
