"use client";

import { AlertTriangle, CheckCircle2, ExternalLink, Pencil } from "lucide-react";

import { Alert, AlertAction, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import type { SocialAccount } from "@/lib/api/types";
import { handleOf } from "@/lib/publishing/rules";
import type { ScheduledPost, ScheduledPostTarget } from "@/lib/publishing/types";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

const TARGET_LABEL: Record<ScheduledPostTarget["status"], string> = {
  pending: "Waiting",
  publishing: "Publishing",
  container_created: "Instagram is processing it",
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

function TargetRows({ targets, accounts, timeZone, now }: { targets: ScheduledPostTarget[]; accounts: SocialAccount[]; timeZone: string; now: Date }) {
  return (
    <ul className="mt-3 space-y-2" aria-label="Accounts">
      {targets.map((target) => {
        const account = accounts.find((item) => item.id === target.social_account_id);
        return (
          <li key={target.social_account_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="font-medium">{handleOf(account)}</span>
            <span className={cn(target.status === "failed" ? "text-danger-fg" : "text-fg-secondary")}>
              {TARGET_LABEL[target.status]}
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
                View on Instagram <ExternalLink className="size-3.5" aria-hidden />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            ) : null}
            <FirstCommentLine target={target} />
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
}: {
  post: ScheduledPost;
  accounts: SocialAccount[];
  timeZone: string;
  now: Date;
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
          <TargetRows targets={post.targets} accounts={accounts} timeZone={timeZone} now={now} />
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
