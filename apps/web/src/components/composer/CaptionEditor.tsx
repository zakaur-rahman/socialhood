"use client";

import { AlertCircle, Hash, Plus, Sparkles, Tags, X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";

import { UpgradeAction } from "@/components/billing/UpgradeAction";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CardInset } from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useGenerateCaption, useSuggestHashtags } from "@/lib/api/queries/scheduledPosts";
import { errorMessage } from "@/lib/copy";
import {
  appendHashtags,
  CAPTION_MAX_CHARS,
  countText,
  FIRST_COMMENT_MAX_CHARS,
  formatCount,
  hashtagsIn,
  MAX_HASHTAGS,
  MAX_MENTIONS,
  SUGGESTED_HASHTAGS_MAX,
} from "@/lib/publishing/rules";
import type { HashtagGroup } from "@/lib/publishing/types";
import { cn } from "@/lib/utils";

import { Section } from "./Section";

type Tools = { ai: boolean; suggest: boolean; groups: boolean };

const CAPTION_TOOLS: Tools = { ai: true, suggest: true, groups: true };

/**
 * One caption box (UX-SCR-13 Caption, FR-PUB-10 counters): characters, hashtags and mentions
 * against Instagram's limits as you type; Write with AI, Suggest hashtags and Insert hashtag
 * group (FR-PUB-02, FR-PUB-12) act on this box. Hashtag groups count toward the 30.
 */
export function CaptionField({
  id,
  label,
  value,
  onChange,
  wid,
  slug,
  groups,
  groupsLoading,
  maxChars = CAPTION_MAX_CHARS,
  mentions = true,
  tools = CAPTION_TOOLS,
  placeholder,
  hint,
  rows = 6,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  wid: string;
  slug: string;
  groups: HashtagGroup[];
  groupsLoading: boolean;
  maxChars?: number;
  /** Count @mentions (captions do; the first comment doesn't). */
  mentions?: boolean;
  tools?: Tools;
  placeholder?: string;
  hint?: string;
  rows?: number;
}) {
  const counts = countText(value);
  const overChars = counts.chars > maxChars;
  const overHashtags = counts.hashtags > MAX_HASHTAGS;
  const overMentions = mentions && counts.mentions > MAX_MENTIONS;
  const [suggested, setSuggested] = useState<string[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // The failure behind the notice: a plan limit (402) gets Upgrade beside it.
  const [noticeError, setNoticeError] = useState<unknown>(null);
  const suggest = useSuggestHashtags(wid);

  const present = new Set(hashtagsIn(value));
  const remaining = (suggested ?? []).filter((tag) => !present.has(tag));

  const onSuggest = () => {
    setNotice(null);
    setNoticeError(null);
    if (!value.trim()) {
      setNotice("Write a caption first, then suggest hashtags.");
      return;
    }
    const exclude = Array.from(present).slice(0, MAX_HASHTAGS);
    suggest.mutate(
      { caption: value, count: SUGGESTED_HASHTAGS_MAX, exclude },
      {
        onSuccess: (result) => {
          setSuggested(result.hashtags);
          if (result.hashtags.length === 0) setNotice("No new hashtags to suggest for this caption.");
        },
        onError: (error) => {
          setNotice(errorMessage(error));
          setNoticeError(error);
        },
      },
    );
  };

  return (
    <Field id={id} invalid={overChars || overHashtags || overMentions || undefined} className="gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <FieldLabel className="text-sm font-medium">{label}</FieldLabel>
        <div className="flex flex-wrap items-center gap-1">
          {tools.ai ? <WriteWithAi wid={wid} caption={value} onWritten={onChange} /> : null}
          {tools.suggest ? (
            <Button type="button" variant="ghost" size="sm" onClick={onSuggest} loading={suggest.isPending}>
              <Hash aria-hidden />
              Suggest hashtags
            </Button>
          ) : null}
          {tools.groups ? (
            <HashtagGroupMenu
              groups={groups}
              loading={groupsLoading}
              slug={slug}
              onInsert={(group) => onChange(appendHashtags(value, group.hashtags))}
            />
          ) : null}
        </div>
      </div>
      <Textarea
        value={value}
        rows={rows}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-28 resize-y"
      />
      <FieldDescription className="flex flex-wrap gap-x-3 gap-y-1 tabular-nums" data-testid={`${id}-counts`}>
        <span className={cn(overChars && "font-medium text-danger-fg")}>
          {formatCount(counts.chars)} / {formatCount(maxChars)} characters
        </span>
        <span className={cn(overHashtags && "font-medium text-danger-fg")}>
          {counts.hashtags} / {MAX_HASHTAGS} hashtags
        </span>
        {mentions ? (
          <span className={cn(overMentions && "font-medium text-danger-fg")}>
            {counts.mentions} / {MAX_MENTIONS} mentions
          </span>
        ) : null}
      </FieldDescription>
      {hint ? <FieldDescription>{hint}</FieldDescription> : null}
      {notice ? (
        <Alert tone="danger" icon={<AlertCircle />} action={<UpgradeAction error={noticeError} />}>
          {notice}
        </Alert>
      ) : null}
      {suggested && remaining.length > 0 ? (
        <CardInset asChild padding="compact">
          <div role="group" aria-label="Suggested hashtags">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-brand-fg">
                <Sparkles className="mr-1 inline size-3.5" aria-hidden />
                Suggested hashtags
              </p>
              <div className="flex gap-1">
                <Button type="button" variant="ghost" size="xs" onClick={() => onChange(appendHashtags(value, remaining))}>
                  <Plus aria-hidden /> Add all
                </Button>
                <Button type="button" variant="ghost" size="icon-xs" aria-label="Dismiss suggested hashtags" onClick={() => setSuggested(null)}>
                  <X aria-hidden />
                </Button>
              </div>
            </div>
            <ul className="flex flex-wrap gap-1.5">
              {remaining.map((tag) => (
                <li key={tag}>
                  <Button
                    type="button"
                    variant="secondary"
                    size="xs"
                    aria-label={`Add #${tag}`}
                    onClick={() => onChange(appendHashtags(value, [tag]))}
                  >
                    #{tag}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        </CardInset>
      ) : null}
    </Field>
  );
}

export const CAPTION_ID = "composer-caption";

export function accountCaptionId(accountId: string): string {
  return `composer-caption-${accountId}`;
}

export type AccountCaption = { accountId: string; label: string; value: string };

/**
 * UX-SCR-13 Caption: one caption for every account, or (with two or more accounts) a caption per
 * account. The per-account switch copies the caption to each account to start from.
 */
export function CaptionEditor({
  wid,
  slug,
  groups,
  groupsLoading,
  caption,
  onCaptionChange,
  perAccount,
  canPerAccount,
  onPerAccountChange,
  accountCaptions,
  onAccountCaptionChange,
}: {
  wid: string;
  slug: string;
  groups: HashtagGroup[];
  groupsLoading: boolean;
  caption: string;
  onCaptionChange: (value: string) => void;
  perAccount: boolean;
  canPerAccount: boolean;
  onPerAccountChange: (on: boolean) => void;
  /** Each selected account's caption, in the post's account order. */
  accountCaptions: AccountCaption[];
  onAccountCaptionChange: (index: number, value: string) => void;
}) {
  const switchId = useId();
  return (
    <Section
      id="composer-caption-section"
      title="Caption"
      aside={
        canPerAccount || perAccount ? (
          <Field id={switchId} orientation="horizontal" density="compact" className="w-auto gap-2">
            <FieldLabel className="font-normal">Different caption per account</FieldLabel>
            <Switch checked={perAccount} onCheckedChange={onPerAccountChange} />
          </Field>
        ) : null
      }
    >
      {perAccount ? (
        <div className="space-y-5">
          {accountCaptions.map((item, index) => (
            <CaptionField
              key={item.accountId}
              id={accountCaptionId(item.accountId)}
              label={`Caption for ${item.label}`}
              value={item.value}
              onChange={(value) => onAccountCaptionChange(index, value)}
              wid={wid}
              slug={slug}
              groups={groups}
              groupsLoading={groupsLoading}
            />
          ))}
        </div>
      ) : (
        <CaptionField
          id={CAPTION_ID}
          label="Caption"
          value={caption}
          onChange={onCaptionChange}
          wid={wid}
          slug={slug}
          groups={groups}
          groupsLoading={groupsLoading}
          placeholder="Write a caption…"
        />
      )}
    </Section>
  );
}

export const FIRST_COMMENT_ID = "composer-first-comment";

/** FR-PUB-11: posted by the account right after the post, often used for hashtags. */
export function FirstCommentEditor({
  wid,
  slug,
  groups,
  groupsLoading,
  value,
  onChange,
}: {
  wid: string;
  slug: string;
  groups: HashtagGroup[];
  groupsLoading: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Section id="composer-first-comment-section" title="First comment (optional)">
      <CaptionField
        id={FIRST_COMMENT_ID}
        label="Comment"
        value={value}
        onChange={onChange}
        wid={wid}
        slug={slug}
        groups={groups}
        groupsLoading={groupsLoading}
        maxChars={FIRST_COMMENT_MAX_CHARS}
        mentions={false}
        tools={{ ai: false, suggest: false, groups: true }}
        rows={3}
        hint="Posted by each account right after the post goes live. If it fails, the post stays published."
      />
    </Section>
  );
}

/**
 * FR-PUB-02: write a caption from a brief, or improve the one written, in the brand voice. The
 * result replaces the caption; the success toast's Undo puts back the one it replaced (UI-ISS-082).
 */
function WriteWithAi({ wid, caption, onWritten }: { wid: string; caption: string; onWritten: (caption: string) => void }) {
  const [open, setOpen] = useState(false);
  const [brief, setBrief] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const generate = useGenerateCaption(wid);
  const briefId = useId();
  // The caption as it is when the result arrives (it can change while the AI writes), and the box
  // to write to then and on Undo.
  const latest = useRef({ caption, onWritten });
  useEffect(() => {
    latest.current = { caption, onWritten };
  });

  const run = (mode: "write" | "improve") => {
    setError(null);
    setFailure(null);
    generate.mutate(mode === "write" ? { mode, brief: brief.trim() } : { mode, caption, brief: brief.trim() || null }, {
      onSuccess: (result) => {
        const previous = latest.current.caption;
        latest.current.onWritten(result.caption);
        setOpen(false);
        setBrief("");
        toast.success(mode === "write" ? "Caption written. Change anything you like." : "Caption improved. Change anything you like.", {
          // Toasts with an action stay 10 s or more (AGENT_CONTEXT §6).
          duration: 10_000,
          action: { label: "Undo", onClick: () => latest.current.onWritten(previous) },
        });
      },
      // A 402 stays here beside the brief (INLINE_PLAN_LIMITS), with Upgrade opening the dialog.
      onError: (caught) => {
        setError(errorMessage(caught));
        setFailure(caught);
      },
    });
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setError(null);
      }}
    >
      <PopoverTrigger asChild>
        <Button type="button" variant="ghost" size="sm" className="text-brand-fg">
          <Sparkles aria-hidden /> Write with AI
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (brief.trim()) run("write");
          }}
        >
          <Field id={briefId}>
            <FieldLabel className="text-sm font-medium">What&apos;s the post about?</FieldLabel>
            <Textarea
              value={brief}
              maxLength={500}
              rows={3}
              placeholder="New linen dresses, 20% off this weekend"
              onChange={(event) => setBrief(event.target.value)}
            />
            <FieldDescription>Written in your brand voice. Uses AI credits.</FieldDescription>
          </Field>
          {error ? (
            <Alert tone="danger" action={<UpgradeAction error={failure} />}>
              {error}
            </Alert>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              disabled={!brief.trim() || generate.isPending}
              loading={generate.isPending && generate.variables?.mode === "write"}
            >
              Write caption
            </Button>
            {caption.trim() ? (
              <Button
                type="button"
                variant="secondary"
                disabled={generate.isPending}
                loading={generate.isPending && generate.variables?.mode === "improve"}
                onClick={() => run("improve")}
              >
                Improve my caption
              </Button>
            ) : null}
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}

/** FR-PUB-12: insert a saved group with a click. Groups are managed on the Schedule page. */
function HashtagGroupMenu({
  groups,
  loading,
  slug,
  onInsert,
}: {
  groups: HashtagGroup[];
  loading: boolean;
  slug: string;
  onInsert: (group: HashtagGroup) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="sm">
          <Tags aria-hidden /> Insert hashtag group
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Hashtag groups</DropdownMenuLabel>
        {loading ? (
          <DropdownMenuItem disabled>Loading…</DropdownMenuItem>
        ) : groups.length === 0 ? (
          <DropdownMenuItem disabled>No hashtag groups yet</DropdownMenuItem>
        ) : (
          groups.map((group) => (
            <DropdownMenuItem key={group.id} onSelect={() => onInsert(group)} className="flex justify-between gap-3">
              <span className="truncate">{group.name}</span>
              <span className="shrink-0 text-xs text-fg-secondary tabular-nums">{group.hashtags.length}</span>
            </DropdownMenuItem>
          ))
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href={`/w/${slug}/schedule` as Route}>Manage hashtag groups</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
