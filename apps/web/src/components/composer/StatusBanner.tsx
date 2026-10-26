"use client";

import { AlertTriangle, CheckCircle2, ExternalLink, Pencil, RotateCw } from "lucide-react";

import { Alert, AlertAction, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRefreshCollaborators } from "@/lib/api/queries/scheduledPosts";
import { usePostPerformance } from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { AGE_LABEL, figuresOf, formatFigure } from "@/lib/analytics/format";
import { handleOf } from "@/lib/publishing/rules";
import type { ScheduledPost, ScheduledPostTarget } from "@/lib/publishing/types";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

/** The platform's name in the words the banner uses. */
function platformName(account: SocialAccount | undefined): string {
  return account?.platform === "facebook" ? "Facebook" : "Instagram";
}

const TARGET_LABEL: Record<ScheduledPostTarget["status"], string> = {
  pending: "Waiting",
  publishing: "Publishing",
  container_created: "Processing",
  published: "Published",
  failed: "Failed",
  canceled: "Cancelled",
};

function FirstCommentLine({ target }: { target: ScheduledPostTarget }) {
  const result = target.first_comment;
  if (!result) return null;
  if (result.status === "posted") return <span className="text-fg-secondary">First comment posted</span>;
  if (result.status === "pending") return <span className="text-fg-secondary">Posting the first comment…</span>;
  return (
    <span className="text-danger-fg">
      First comment didn&apos;t post{result.error ? `: ${result.error}` : "."}
    </span>
  );
}

/**
 * FR-PUB-07: each collaborator's invite on a published post, Pending until they accept. Read from
 * Instagram every hour for three days, or now with Refresh. Collaborators can't be changed once the
 * post is published.
 */
function CollaboratorLine({ target, wid, postId, timeZone, now }: { target: ScheduledPostTarget; wid?: string; postId: string; timeZone: string; now: Date }) {
  const refresh = useRefreshCollaborators(wid ?? "", postId);
  const list = target.collaborators ?? [];
  if (target.status !== "published" || list.length === 0) return null;
  return (
    <span className="flex basis-full flex-wrap items-center gap-x-3 gap-y-1 text-fg-secondary" data-testid="collaborator-status">
      <span>Collaborators:</span>
      <ul className="flex flex-wrap gap-x-3" aria-label="Collaborators">
        {list.map((item) => (
          <li key={item.username} data-testid={`collaborator-${item.username}`}>
            @{item.username} <span className={item.status === "accepted" ? "text-success" : undefined}>{item.status === "accepted" ? "Accepted" : "Pending"}</span>
          </li>
        ))}
      </ul>
      {wid ? (
        <Button type="button" variant="ghost" size="xs" loading={refresh.isPending} onClick={() => refresh.mutate()}>
          <RotateCw aria-hidden /> Refresh
        </Button>
      ) : null}
      <span className="text-xs">
        {target.collaborators_checked_at ? `Checked ${formatDayTime(target.collaborators_checked_at, timeZone, now)}. ` : "Not checked yet. "}
        They can&apos;t be changed after publishing.
      </span>
    </span>
  );
}

/** The figures read so far for a published Story (1 h, 6 h and 23 h, before it goes down). */
const STORY_SUMMARY = ["reach", "views", "replies", "shares"] as const;

function StoryInsights({ wid, postId }: { wid: string; postId: string }) {
  const performance = usePostPerformance(wid, postId, null);
  if (!performance.data) return null;
  const { data } = performance;
  if (!data.captured_at) {
    return (
      <span className="text-fg-secondary" data-testid="story-insights">
        Figures are read 1 h after it goes up
      </span>
    );
  }
  const figures = figuresOf(data).filter((figure) => (STORY_SUMMARY as readonly string[]).includes(figure.key) && figure.value != null);
  if (figures.length === 0) {
    return (
      <span className="text-fg-secondary" data-testid="story-insights">
        {data.insights_granted ? "No figures from Instagram yet" : "Reconnect to read Story insights"}
      </span>
    );
  }
  return (
    <span className="text-fg-secondary" data-testid="story-insights">
      {figures.map((figure) => `${figure.label} ${formatFigure(figure)}`).join(" · ")} · at {AGE_LABEL[data.age]}
    </span>
  );
}

function TargetRows({
  targets,
  accounts,
  timeZone,
  now,
  wid,
  postId,
}: {
  postId?: string;
  targets: ScheduledPostTarget[];
  accounts: SocialAccount[];
  timeZone: string;
  now: Date;
  wid?: string;
}) {
  return (
    <ul className="mt-3 space-y-2" aria-label="Accounts">
      {targets.map((target) => {
        const account = accounts.find((item) => item.id === target.social_account_id);
        return (
          <li key={target.social_account_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="font-medium">{handleOf(account)}</span>
            <span className={cn(target.status === "failed" ? "text-danger-fg" : "text-fg-secondary")}>
              {target.status === "container_created" ? `${platformName(account)} is processing it` : TARGET_LABEL[target.status]}
              {target.status === "published" && target.published_at ? ` ${formatDayTime(target.published_at, timeZone, now)}` : ""}
              {target.status === "failed" && target.error ? `: ${target.error.message}` : ""}
            </span>
            {target.permalink ? (
              <a
                href={target.permalink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-brand-fg underline-offset-4 hover:underline"
              >
                View on {platformName(account)} <ExternalLink className="size-3.5" aria-hidden />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            ) : null}
            {target.expires_at ? (
              <span className="text-fg-secondary" data-testid="story-expiry">
                {new Date(target.expires_at).getTime() > now.getTime()
                  ? `Disappears ${formatDayTime(target.expires_at, timeZone, now)}`
                  : "Expired after 24 hours"}
              </span>
            ) : null}
            {wid && target.expires_at && target.status === "published" && target.post_id ? (
              account?.platform === "facebook" ? (
                <span className="text-fg-secondary" data-testid="story-insights">
                  Facebook doesn&apos;t share figures for Page Stories
                </span>
              ) : (
                <StoryInsights wid={wid} postId={target.post_id} />
              )
            ) : null}
            <FirstCommentLine target={target} />
            {postId ? <CollaboratorLine target={target} wid={wid} postId={postId} timeZone={timeZone} now={now} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * UX-SCR-13: while publishing the composer is read-only under a status banner; a published post
 * shows View on Instagram and the first-comment result; a failed or cancelled one shows the reason
 * and Edit and retry.
 */
export function StatusBanner({
  post,
  accounts,
  timeZone,
  now,
  onEditAndRetry,
  retrying,
  wid,
}: {
  post: ScheduledPost;
  accounts: SocialAccount[];
  timeZone: string;
  now: Date;
  /** The workspace, to read a published Story's insights. */
  wid?: string;
  onEditAndRetry: () => void;
  retrying: boolean;
}) {
  switch (post.status) {
    case "draft":
    case "scheduled":
      return null;
    case "publishing":
      return (
        <Alert variant="outline" tone="brand" data-testid="status-banner" className="mt-4" icon={<Spinner />}>
          <AlertTitle>Publishing started. The post can&apos;t be changed now.</AlertTitle>
          <TargetRows targets={post.targets} accounts={accounts} timeZone={timeZone} now={now} />
        </Alert>
      );
    case "published":
    case "partially_published":
      return (
        <Alert
          variant="outline"
          tone={post.status === "published" ? "success" : "warning"}
          data-testid="status-banner"
          className="mt-4"
          icon={<CheckCircle2 />}
        >
          <AlertTitle>
            {post.status === "published" ? "Published" : "Partly published"}
            {post.published_at ? ` ${formatDayTime(post.published_at, timeZone, now)}` : ""}
          </AlertTitle>
          <TargetRows targets={post.targets} accounts={accounts} timeZone={timeZone} now={now} wid={wid} postId={post.id} />
        </Alert>
      );
    case "failed":
    case "canceled":
      return (
        <Alert
          variant="outline"
          tone="danger"
          data-testid="status-banner"
          className="mt-4"
          icon={<AlertTriangle />}
          action={
            <AlertAction onClick={onEditAndRetry} loading={retrying}>
              <Pencil aria-hidden /> Edit and retry
            </AlertAction>
          }
        >
          <AlertTitle>{post.status === "failed" ? "This post didn't publish." : "This post was cancelled."}</AlertTitle>
          <TargetRows targets={post.targets} accounts={accounts} timeZone={timeZone} now={now} />
        </Alert>
      );
  }
}
