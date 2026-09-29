"use client";

import { Eye, EyeOff, MessageCircle, Reply, Send, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { IntentChip } from "@/components/ai/AnalysisChips";
import { ContactAvatar } from "@/components/inbox/ContactAvatar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useDeleteComment, usePrivateReply, useReplyToComment, useSetCommentHidden } from "@/lib/api/queries";
import type { PostComment } from "@/lib/api/types";
import { SENTIMENT_DOT, SENTIMENT_LABEL } from "@/lib/ai/format";
import { authorHandle, authorName, commentActionError } from "@/lib/comments/format";
import { TONE_CLASS } from "@/lib/inbox/format";
import { relativeTime } from "@/lib/time";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { CommentComposer, type ComposerKind } from "./CommentComposer";

const CHIP = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium";
/** Always visible (UX-A11Y-02); 40 px targets on phones (UX-A11Y-05). */
const ACTION = "min-h-10 px-2.5 text-fg-secondary hover:text-fg md:min-h-7";

function when(iso: string, now: Date): string {
  const relative = relativeTime(iso, now);
  if (relative === "now") return "just now";
  return /^\d+[mhd]$/.test(relative) ? `${relative} ago` : relative;
}

/**
 * UX-SCR-05 comment row: avatar, @username, time, text, sentiment dot and intent chip, and the
 * actions Reply (inline composer), DM (the one private reply), Hide or Unhide, and Delete for
 * admins after a confirm. Each answer patches the lists; comment.updated does the same live.
 */
export function CommentRow({
  comment,
  wid,
  slug,
  timeZone,
  now,
  canDelete,
  accountUsername,
}: {
  comment: PostComment;
  wid: string;
  slug: string;
  timeZone: string;
  now: Date;
  canDelete: boolean;
  /** The post's account, for error copy ("@maple needs reconnecting…"). */
  accountUsername?: string | null;
}) {
  const [composer, setComposer] = useState<ComposerKind | null>(null);
  const [composerError, setComposerError] = useState<string | null>(null);
  const reply = useReplyToComment(wid);
  const dm = usePrivateReply(wid);
  const setHidden = useSetCommentHidden(wid);
  const remove = useDeleteComment(wid);
  const name = authorName(comment);
  const handle = authorHandle(comment);
  const analysis = comment.analysis ?? null;

  const open = (kind: ComposerKind) => {
    setComposerError(null);
    setComposer((current) => (current === kind ? null : kind));
  };

  const send = (text: string, idempotencyKey: string) => {
    setComposerError(null);
    const kind = composer;
    const mutation = kind === "dm" ? dm : reply;
    mutation.mutate(
      { comment, text, idempotencyKey },
      {
        onSuccess: () => {
          setComposer(null);
          toast.success(kind === "dm" ? `DM on its way to ${handle}` : "Reply posted");
        },
        onError: (error) => setComposerError(commentActionError(error, kind === "dm" ? "dm" : "reply", accountUsername)),
      },
    );
  };

  const toggleHidden = () => {
    const hidden = !comment.hidden;
    setHidden.mutate(
      { comment, hidden },
      {
        onSuccess: () =>
          toast.success(hidden ? "Comment hidden. Only its author can still see it." : "Comment shown again"),
        onError: (error) => toast.error(commentActionError(error, hidden ? "hide" : "unhide", accountUsername)),
      },
    );
  };

  const confirmDelete = () =>
    remove.mutate(comment, {
      onSuccess: () => toast.success("Comment deleted"),
      onError: (error) => toast.error(commentActionError(error, "delete", accountUsername)),
    });

  return (
    <li
      className="flex gap-3 border-b border-line-subtle px-4 py-3 last:border-b-0"
      data-testid="comment-row"
      data-comment-id={comment.id}
      aria-label={`Comment by ${name}`}
    >
      <ContactAvatar
        id={comment.contact_id ?? comment.author_username ?? comment.id}
        name={comment.author_username ?? "?"}
        pictureUrl={comment.author_profile_picture_url}
        size={32}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-medium">{name}</span>
          <time
            dateTime={comment.commented_at}
            title={formatDayTime(comment.commented_at, timeZone, now)}
            className="text-xs text-fg-secondary"
          >
            {when(comment.commented_at, now)}
          </time>
          {analysis && !analysis.is_spam ? (
            <>
              <span
                role="img"
                aria-label={`${SENTIMENT_LABEL[analysis.sentiment]} sentiment`}
                data-sentiment={analysis.sentiment}
                className={cn("size-2 rounded-full", SENTIMENT_DOT[analysis.sentiment])}
              />
              <IntentChip intent={analysis.intent} />
            </>
          ) : null}
          {analysis?.is_spam ? <span className={cn(CHIP, TONE_CLASS.warning)}>Spam</span> : null}
          {comment.hidden ? (
            <span className={cn(CHIP, TONE_CLASS.neutral)}>
              <EyeOff className="size-3" aria-hidden /> Hidden
            </span>
          ) : null}
        </div>
        {comment.parent_platform_comment_id ? (
          <p className="mt-0.5 text-xs text-fg-secondary">Reply in a thread</p>
        ) : null}
        <p className={cn("mt-1 text-sm break-words whitespace-pre-wrap", comment.hidden && "text-fg-secondary")}>
          {comment.text}
        </p>

        {comment.public_reply ? (
          <div className="mt-2 border-l-2 border-brand-line pl-3" data-testid="public-reply">
            <p className="text-xs text-fg-secondary">
              Your public reply · {when(comment.public_reply.replied_at, now)}
            </p>
            <p className="text-sm break-words whitespace-pre-wrap">{comment.public_reply.text}</p>
          </div>
        ) : null}

        <div className="mt-1 -ml-2.5 flex flex-wrap items-center gap-x-1" role="group" aria-label={`Actions for ${name}'s comment`}>
          <Button
            variant="ghost"
            size="sm"
            className={cn(ACTION, composer === "reply" && "text-brand-fg")}
            aria-label={`Reply to ${name}`}
            aria-expanded={composer === "reply"}
            onClick={() => open("reply")}
          >
            <Reply aria-hidden /> Reply
          </Button>
          {comment.private_reply ? (
            <Button asChild variant="ghost" size="sm" className={ACTION}>
              <Link href={`/w/${slug}/inbox/${comment.private_reply.conversation_id}` as Route} aria-label={`View DM to ${name}`}>
                <MessageCircle aria-hidden /> View DM
              </Link>
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className={cn(ACTION, composer === "dm" && "text-brand-fg")}
              aria-label={`DM ${name}`}
              aria-expanded={composer === "dm"}
              onClick={() => open("dm")}
            >
              <Send aria-hidden /> DM
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className={ACTION}
            aria-label={comment.hidden ? `Unhide ${name}'s comment` : `Hide ${name}'s comment`}
            disabled={setHidden.isPending}
            onClick={toggleHidden}
          >
            {comment.hidden ? <Eye aria-hidden /> : <EyeOff aria-hidden />}
            {comment.hidden ? "Unhide" : "Hide"}
          </Button>
          {canDelete ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(ACTION, "hover:text-danger-fg")}
                  aria-label={`Delete ${name}'s comment`}
                  disabled={remove.isPending}
                >
                  <Trash2 aria-hidden /> Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="border-line bg-panel">
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete this comment?</AlertDialogTitle>
                  <AlertDialogDescription className="text-fg-secondary">
                    It&apos;s deleted on Instagram for everyone, {handle} included. This can&apos;t be undone. To keep it
                    but stop others seeing it, hide it instead.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={confirmDelete} className="bg-danger-fill text-white hover:bg-danger-fill/90">
                    Delete comment
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
        </div>
        {comment.private_reply ? <p className="text-xs text-fg-secondary">DM sent to {handle}</p> : null}

        {composer ? (
          <CommentComposer
            key={composer}
            kind={composer}
            comment={comment}
            pending={composer === "dm" ? dm.isPending : reply.isPending}
            error={composerError}
            onSend={send}
            onCancel={() => {
              setComposer(null);
              setComposerError(null);
            }}
          />
        ) : null}
      </div>
    </li>
  );
}
