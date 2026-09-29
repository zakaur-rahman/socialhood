"use client";

import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, type ReactNode } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { useSocialAccounts } from "@/lib/api/queries";
import { useCreateScheduledPost } from "@/lib/api/queries/scheduledPosts";
import type { SocialAccount } from "@/lib/api/types";
import { cannotPublishReason, MIN_SCHEDULE_LEAD_MS, publishingAccounts } from "@/lib/publishing/rules";
import type { ScheduledPostDraft } from "@/lib/publishing/types";
import { useCurrentWorkspace } from "@/lib/workspace";

import { composerHref } from "./PostComposer";

/**
 * The new draft (F-13): an empty post, with the time of a calendar click (``at``, an ISO instant
 * at least 5 minutes away) and the only account when just one can publish.
 */
export function newDraftBody(accounts: SocialAccount[], at: string | null, now: Date): ScheduledPostDraft {
  const ready = publishingAccounts(accounts).filter((account) => !cannotPublishReason(account));
  const time = at ? new Date(at) : null;
  const publishAt = time && !Number.isNaN(time.getTime()) && time.getTime() - now.getTime() >= MIN_SCHEDULE_LEAD_MS ? time.toISOString() : null;
  return {
    targets: ready.length === 1 ? [{ social_account_id: ready[0].id, caption_override: null }] : [],
    asset_ids: [],
    caption: "",
    first_comment: null,
    publish_at: publishAt,
  };
}

/**
 * /schedule/new: creates the draft, then replaces the URL with the composer's, so Back returns
 * to where New post was clicked. The Schedule page can also create the draft itself with
 * useCreateScheduledPost and open composerHref.
 */
export function NewPost({ at }: { at: string | null }) {
  const workspace = useCurrentWorkspace();
  const router = useRouter();
  const accounts = useSocialAccounts(workspace.id);
  const create = useCreateScheduledPost(workspace.id);
  const { mutate } = create;
  const started = useRef(false);

  const start = useCallback(
    (list: SocialAccount[]) =>
      mutate(newDraftBody(list, at, new Date()), {
        onSuccess: (post) => router.replace(composerHref(workspace.slug, post.id)),
      }),
    [at, mutate, router, workspace.slug],
  );

  const loaded = accounts.isSuccess || accounts.isError;
  const list = accounts.data;
  useEffect(() => {
    // Once, even when effects run twice in development.
    if (!loaded || started.current) return;
    started.current = true;
    start(list ?? []);
  }, [list, loaded, start]);

  if (create.isError) return <ErrorState error={create.error} onRetry={() => start(list ?? [])} />;
  return <PageSkeleton rows={3} />;
}

/** Scheduling is for owners and admins (§2.15); an agent following a link is told so. */
export function AdminOnly({ children }: { children: ReactNode }) {
  const workspace = useCurrentWorkspace();
  if (workspace.role !== "agent") return children;
  return (
    <EmptyState
      className="min-h-[60vh]"
      title="Scheduling is for owners and admins"
      body="Ask an owner or admin of this workspace to schedule posts."
      action={
        <Link href={`/w/${workspace.slug}/home` as Route} className="text-sm text-brand-fg underline-offset-4 hover:underline">
          Go to Home
        </Link>
      }
    />
  );
}
