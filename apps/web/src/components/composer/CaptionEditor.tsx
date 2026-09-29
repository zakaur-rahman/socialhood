"use client";

import { AlertCircle, Hash, Loader2, Plus, Sparkles, Tags, X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useId, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
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
  const countsId = useId();
  const hintId = useId();
  const counts = countText(value);
  const overChars = counts.chars > maxChars;
  const overHashtags = counts.hashtags > MAX_HASHTAGS;
  const overMentions = mentions && counts.mentions > MAX_MENTIONS;
  const [suggested, setSuggested] = useState<string[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const suggest = useSuggestHashtags(wid);

  const present = new Set(hashtagsIn(value));
  const remaining = (suggested ?? []).filter((tag) => !present.has(tag));

  const onSuggest = () => {
    setNotice(null);
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
        onError: (error) => setNotice(errorMessage(error)),
      },
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Label htmlFor={id} className="text-sm font-medium">
          {label}
        </Label>
        <div className="flex flex-wrap items-center gap-1">
          {tools.ai ? <WriteWithAi wid={wid} caption={value} onWritten={onChange} /> : null}
          {tools.suggest ? (
            <Button type="button" variant="ghost" size="sm" className="h-10 md:h-7" onClick={onSuggest} disabled={suggest.isPending}>
              {suggest.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Hash aria-hidden />}
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
        id={id}
        value={value}
        rows={rows}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={overChars || overHashtags || overMentions ? true : undefined}
        aria-describedby={hint ? `${countsId} ${hintId}` : countsId}
        className="min-h-28 resize-y bg-field text-sm focus:bg-raised"
      />
      <p id={countsId} className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-fg-secondary tabular-nums" data-testid={`${id}-counts`}>
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
      </p>
      {hint ? (
        <p id={hintId} className="text-xs text-fg-secondary">
          {hint}
        </p>
      ) : null}
      {notice ? (
        <p role="alert" className="flex items-start gap-1.5 text-xs text-danger-fg">
          <AlertCircle className="mt-px size-3.5 shrink-0" aria-hidden /> {notice}
        </p>
      ) : null}
      {suggested && remaining.length > 0 ? (
        <div role="group" aria-label="Suggested hashtags" className="rounded-lg border border-line bg-field p-3">
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
                <button
                  type="button"
                  aria-label={`Add #${tag}`}
                  onClick={() => onChange(appendHashtags(value, [tag]))}
                  className="min-h-10 rounded-full bg-raised px-2.5 text-xs text-fg hover:bg-raised-hover md:min-h-8"
                >
                  #{tag}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
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
          <div className="flex items-center gap-2">
            <Label htmlFor={switchId} className="text-xs font-normal text-fg-secondary">
              Different caption per account
            </Label>
            <Switch id={switchId} checked={perAccount} onCheckedChange={onPerAccountChange} />
          </div>
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

/** FR-PUB-02: write a caption from a brief, or improve the one written, in the brand voice. */
function WriteWithAi({ wid, caption, onWritten }: { wid: string; caption: string; onWritten: (caption: string) => void }) {
  const [open, setOpen] = useState(false);
  const [brief, setBrief] = useState("");
  const [error, setError] = useState<string | null>(null);
  const generate = useGenerateCaption(wid);
  const briefId = useId();

  const run = (mode: "write" | "improve") => {
    setError(null);
    generate.mutate(mode === "write" ? { mode, brief: brief.trim() } : { mode, caption, brief: brief.trim() || null }, {
      onSuccess: (result) => {
        onWritten(result.caption);
        setOpen(false);
        setBrief("");
        toast.success(mode === "write" ? "Caption written. Change anything you like." : "Caption improved. Change anything you like.");
      },
      onError: (caught) => setError(errorMessage(caught)),
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
        <Button type="button" variant="ghost" size="sm" className="h-10 text-brand-fg md:h-7">
          <Sparkles aria-hidden /> Write with AI
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 border-line bg-panel">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (brief.trim()) run("write");
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor={briefId} className="text-sm font-medium">
              What&apos;s the post about?
            </Label>
            <Textarea
              id={briefId}
              value={brief}
              maxLength={500}
              rows={3}
              placeholder="New linen dresses, 20% off this weekend"
              onChange={(event) => setBrief(event.target.value)}
              className="bg-field text-sm"
            />
            <p className="text-xs text-fg-secondary">Written in your brand voice. Uses AI credits.</p>
          </div>
          {error ? (
            <p role="alert" className="text-xs text-danger-fg">
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" className="bg-brand-gradient text-white" disabled={!brief.trim() || generate.isPending}>
              {generate.isPending && generate.variables?.mode === "write" ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Write caption
            </Button>
            {caption.trim() ? (
              <Button type="button" variant="secondary" disabled={generate.isPending} onClick={() => run("improve")}>
                {generate.isPending && generate.variables?.mode === "improve" ? <Loader2 className="animate-spin" aria-hidden /> : null}
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
        <Button type="button" variant="ghost" size="sm" className="h-10 md:h-7">
          <Tags aria-hidden /> Insert hashtag group
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 border-line bg-panel shadow-xl">
        <DropdownMenuLabel className="text-xs text-fg-secondary">Hashtag groups</DropdownMenuLabel>
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
