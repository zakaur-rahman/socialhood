"use client";

import { Clock, Heart, Paperclip, SendHorizontal, Smile, Sticker } from "lucide-react";
import type { Route } from "next";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { toast } from "sonner";

import { UpgradeAction } from "@/components/billing/UpgradeAction";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/lib/api/provider";
import { useCreateScheduled, type ReplyInput } from "@/lib/api/queries";
import type { Conversation, MediaAsset } from "@/lib/api/types";
import { composerCopy, errorMessage } from "@/lib/copy";
import { contactName, firstName, timeLeft } from "@/lib/inbox/format";
import { useInboxStore } from "@/lib/inbox/store";
import { ATTACHMENT_RULES, STICKER_RULE, UploadError, uploadAsset } from "@/lib/media/upload";
import { relativeTime } from "@/lib/time";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";
import { uuid } from "@/lib/uuid";

import { AttachmentTray, type TrayItem } from "./AttachmentTray";
import {
  checkSchedule,
  defaultSchedule,
  preparedSchedule,
  ScheduleFields,
  scheduleLimits,
  type ScheduleValue,
} from "./ScheduleFields";

// TR-FE-08: the emoji picker loads on demand.
const EmojiPicker = dynamic(() => import("./EmojiPicker"), {
  ssr: false,
  loading: () => <Skeleton className="h-64 w-72 bg-raised" />,
});

const MIN_HEIGHT = 40;
const MAX_HEIGHT = 160;
const MAX_ATTACHMENTS = 10;

export type Uploader = (
  file: File,
  options: { onProgress: (fraction: number) => void; signal: AbortSignal },
) => Promise<MediaAsset>;

type Props = {
  wid: string;
  slug: string;
  timeZone: string;
  conversation: Conversation;
  /** When the customer last wrote, for the closed-window notice. */
  lastInboundAt: string | null;
  now: Date;
  onSend: (input: ReplyInput) => void;
  scheduleOpen: boolean;
  onScheduleOpenChange: (open: boolean) => void;
  /** A time prepared by Ask Social Hood (FR-AGT-03): the popover opens at it when it fits. */
  scheduleAt?: string | null;
  onChooseTemplate: () => void;
  /** The account can send attachments (capability dm_attachments). */
  canAttach: boolean;
  /** Tests inject a fake; the app uploads through the API and Cloudinary. */
  upload?: Uploader;
  /** With a suggestion showing: Ctrl/⌘ Enter sends it and Esc dismisses it from an empty composer (UX-INB-08). */
  suggestionKeys?: { send: () => void; dismiss: () => void } | null;
};

type Mode = "reply" | "blocked" | "closed" | "template_only";

/**
 * UX-INB-07, F-07: autosizing textarea (40–160 px, reset after send), Enter sends and
 * Shift+Enter adds a line, lazy emoji, attachments, scheduling, and the window states.
 * The draft lives in the store by conversation id (TR-FE-06).
 */
export function Composer({
  wid,
  slug,
  timeZone,
  conversation,
  lastInboundAt,
  now,
  onSend,
  scheduleOpen,
  onScheduleOpenChange,
  scheduleAt = null,
  onChooseTemplate,
  canAttach,
  upload,
  suggestionKeys = null,
}: Props) {
  const conversationId = conversation.id;
  const draft = useInboxStore((state) => state.drafts[conversationId] ?? "");
  const setDraft = useInboxStore((state) => state.setDraft);
  // F-08 Edit: the suggestion whose text is in the box goes with the reply as suggestion_id.
  const editingSuggestion = useInboxStore((state) => state.suggestionEdits[conversationId] ?? null);
  const setSuggestionEdit = useInboxStore((state) => state.setSuggestionEdit);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const stickerRef = useRef<HTMLInputElement>(null);
  const tray = useAttachmentTray(wid, upload);
  const sticker = useStickerUpload(wid, upload);

  const name = contactName(conversation.contact, conversation.platform);
  const replyWindow = conversation.reply_window;
  const accountStatus = conversation.social_account.status;
  const accountHandle = conversation.social_account.username
    ? `@${conversation.social_account.username}`
    : (conversation.social_account.display_name ?? "This account");
  const mode: Mode =
    accountStatus === "needs_reconnect" || accountStatus === "disconnected"
      ? "blocked"
      : replyWindow.state === "closed"
        ? "closed"
        : replyWindow.state === "template_only"
          ? "template_only"
          : "reply";

  const resize = useCallback(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, el.scrollHeight))}px`;
  }, []);

  // A restored draft opens at its height.
  useLayoutEffect(() => {
    if (textRef.current?.value) resize();
  }, [resize]);

  const ready = tray.items.filter((item) => item.status === "done");
  const uploading = tray.items.some((item) => item.status === "uploading");
  const canSend = mode === "reply" && !uploading && (draft.trim() !== "" || ready.length > 0);

  const resetAfterSend = () => {
    setDraft(conversationId, "");
    tray.clear();
    const el = textRef.current;
    if (el) el.style.height = ""; // back to the 40 px minimum (v1 kept the tall box)
  };

  const send = () => {
    if (!canSend) return;
    onSend({
      text: draft,
      assets: ready.map((item) => item.asset!).filter(Boolean),
      humanAgent: replyWindow.state === "human_agent",
      ...(editingSuggestion ? { suggestionId: editingSuggestion } : {}),
    });
    if (editingSuggestion) setSuggestionEdit(conversationId, null);
    resetAfterSend();
    textRef.current?.focus();
  };

  // Stickers go on their own, straight away (the draft stays for the next message).
  const sendHeart = () => onSend({ heart: true, humanAgent: replyWindow.state === "human_agent" });
  const onStickerFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const asset = await sticker.upload(file);
    if (asset) onSend({ sticker: asset, humanAgent: replyWindow.state === "human_agent" });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestionKeys && draft.trim() === "" && !event.nativeEvent.isComposing) {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        suggestionKeys.send();
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        suggestionKeys.dismiss();
        return;
      }
    }
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (scheduleOpen) return; // with the schedule popover open, Enter does not send
    send();
  };

  const insertEmoji = (emoji: string) => {
    const el = textRef.current;
    const start = el?.selectionStart ?? draft.length;
    const end = el?.selectionEnd ?? draft.length;
    const next = draft.slice(0, start) + emoji + draft.slice(end);
    setDraft(conversationId, next);
    setEmojiOpen(false);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      el.setSelectionRange(start + emoji.length, start + emoji.length);
      resize();
    });
  };

  const onFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    const room = MAX_ATTACHMENTS - tray.items.length;
    if (files.length > room) toast.error(`Up to ${MAX_ATTACHMENTS} attachments per message.`);
    for (const file of files.slice(0, Math.max(0, room))) {
      const problem = ATTACHMENT_RULES[conversation.platform].check(file);
      if (problem) {
        toast.error(`${file.name}: ${problem}`);
        continue;
      }
      tray.add(file);
    }
  };

  if (mode !== "reply") {
    return (
      <div className="shrink-0 border-t border-line bg-panel px-4 py-3" data-mode={mode}>
        <div className="flex flex-wrap items-center gap-3 rounded-lg bg-field px-4 py-3 text-sm" role="status">
          <p className="min-w-0 flex-1 text-fg-secondary">
            {mode === "blocked"
              ? accountStatus === "disconnected"
                ? composerCopy.disconnected(accountHandle)
                : composerCopy.needsReconnect(accountHandle)
              : mode === "closed"
                ? composerCopy.closed(firstName(name), lastInboundAt ? `${relativeTime(lastInboundAt, now)} ago` : null)
                : composerCopy.templateOnly}
          </p>
          {mode === "blocked" ? (
            <Button asChild size="sm" className="bg-brand-gradient text-white">
              <Link href={`/w/${slug}/settings/connections` as Route}>Reconnect</Link>
            </Button>
          ) : mode === "template_only" ? (
            <Button size="sm" className="bg-brand-gradient text-white" onClick={onChooseTemplate}>
              Choose template
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="shrink-0 border-t border-line bg-panel px-4 py-3" data-mode={mode}>
      <AttachmentTray items={tray.items} onRemove={tray.remove} onRetry={tray.retry} />
      <div className="flex items-end gap-2">
        {canAttach ? (
          <>
            <Button
              variant="ghost"
              size="icon-lg"
              className="size-10 rounded-full text-fg-secondary md:size-9"
              aria-label="Attach files"
              onClick={() => fileRef.current?.click()}
            >
              <Paperclip aria-hidden />
            </Button>
            <input
              ref={fileRef}
              type="file"
              multiple
              hidden
              accept={ATTACHMENT_RULES[conversation.platform].accept}
              onChange={onFiles}
              data-testid="composer-file-input"
            />
          </>
        ) : null}
        <label htmlFor={`composer-${conversationId}`} className="sr-only">
          Reply to {name}
        </label>
        <textarea
          ref={textRef}
          id={`composer-${conversationId}`}
          rows={1}
          value={draft}
          onChange={(event) => {
            setDraft(conversationId, event.target.value);
            resize();
          }}
          onKeyDown={onKeyDown}
          placeholder={`Reply to ${firstName(name)}…`}
          maxLength={4096}
          className="min-h-10 max-h-40 flex-1 resize-none rounded-[20px] border border-line bg-field px-4 py-2 text-sm leading-relaxed outline-none focus:bg-raised"
        />
        {conversation.platform === "instagram" ? (
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-10 rounded-full text-fg-secondary md:size-9"
            aria-label="Send a heart"
            onClick={sendHeart}
          >
            <Heart aria-hidden />
          </Button>
        ) : canAttach ? (
          <>
            <Button
              variant="ghost"
              size="icon-lg"
              className="size-10 rounded-full text-fg-secondary md:size-9"
              aria-label="Send a sticker"
              disabled={sticker.busy}
              onClick={() => stickerRef.current?.click()}
            >
              <Sticker aria-hidden />
            </Button>
            <input
              ref={stickerRef}
              type="file"
              hidden
              accept={STICKER_RULE.accept}
              onChange={(event) => void onStickerFile(event)}
              data-testid="composer-sticker-input"
            />
          </>
        ) : null}
        <Popover open={emojiOpen} onOpenChange={setEmojiOpen}>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon-lg" className="size-10 rounded-full text-fg-secondary md:size-9" aria-label="Add emoji">
              <Smile aria-hidden />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" side="top" className="w-auto border-line bg-panel p-2 shadow-xl">
            {emojiOpen ? <EmojiPicker onPick={insertEmoji} /> : null}
          </PopoverContent>
        </Popover>
        <Popover open={scheduleOpen} onOpenChange={onScheduleOpenChange}>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon-lg" className="size-10 rounded-full text-fg-secondary md:size-9" aria-label="Schedule for later">
              <Clock aria-hidden />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" side="top" className="w-80 border-line bg-panel p-3 shadow-xl">
            {scheduleOpen ? (
              <SchedulePanel
                key={scheduleAt ?? "default"}
                wid={wid}
                conversation={conversation}
                timeZone={timeZone}
                now={now}
                text={draft}
                assets={ready.map((item) => item.asset!).filter(Boolean)}
                blocked={uploading}
                initialAt={scheduleAt}
                onScheduled={() => {
                  resetAfterSend();
                  onScheduleOpenChange(false);
                }}
              />
            ) : null}
          </PopoverContent>
        </Popover>
        <button
          type="button"
          onClick={send}
          disabled={!canSend}
          aria-label="Send"
          className={cn(
            "grid size-10 shrink-0 place-items-center rounded-full md:size-9",
            canSend
              ? "bg-brand-gradient text-white motion-safe:animate-in motion-safe:zoom-in-75 motion-safe:duration-[120ms]"
              : "bg-raised text-fg-disabled",
          )}
        >
          <SendHorizontal className="size-4" aria-hidden />
        </button>
      </div>
      {replyWindow.state === "human_agent" && replyWindow.closes_at ? (
        <p className="mt-2 text-xs text-fg-secondary">{composerCopy.humanAgent(timeLeft(replyWindow.closes_at, now))}</p>
      ) : null}
    </div>
  );
}

/** F-10: pick a time inside the reply window, in the workspace timezone. */
export function SchedulePanel({
  wid,
  conversation,
  timeZone,
  now,
  text,
  assets,
  blocked,
  initialAt = null,
  onScheduled,
}: {
  wid: string;
  conversation: Conversation;
  timeZone: string;
  now: Date;
  text: string;
  assets: MediaAsset[];
  blocked: boolean;
  /** Ask Social Hood's prepared time (FR-AGT-03), used when it is still inside the limits. */
  initialAt?: string | null;
  onScheduled: () => void;
}) {
  const create = useCreateScheduled(wid, conversation.id);
  const closesAt = conversation.reply_window.closes_at ?? null;
  const limits = scheduleLimits(now, closesAt);
  const [prepared] = useState(() => preparedSchedule(initialAt, timeZone, limits));
  const [value, setValue] = useState<ScheduleValue>(() => prepared ?? defaultSchedule(now, timeZone, limits));
  const [error, setError] = useState<string | null>(null);
  // A plan limit (402) behind the error: Upgrade beside it opens the dialog (INLINE_PLAN_LIMITS).
  const [limitError, setLimitError] = useState<unknown>(null);
  const [key] = useState(uuid); // one Idempotency-Key per popover, reused if Schedule is clicked twice
  const windowTooShort = limits.max !== null && limits.max <= limits.min;
  const hasText = text.trim() !== "";

  const schedule = () => {
    const checked = checkSchedule(value, timeZone, limits, now);
    if ("error" in checked) return setError(checked.error);
    setError(null);
    setLimitError(null);
    create.mutate(
      {
        text: text.trim(),
        send_at: checked.at.toISOString(),
        attachment_asset_ids: assets.map((asset) => asset.id),
        idempotencyKey: key,
      },
      {
        onSuccess: (scheduled) => {
          toast.success(`Scheduled for ${formatDayTime(scheduled.send_at, timeZone, now)}`);
          onScheduled();
        },
        onError: (e) => {
          setError(errorMessage(e));
          setLimitError(e);
        },
      },
    );
  };

  return (
    <div className="space-y-3" aria-label="Schedule message">
      <p className="text-sm font-semibold">Schedule message</p>
      {initialAt ? (
        <p className="text-xs text-brand-fg">
          {prepared
            ? "Prepared by Ask Social Hood. Check the message and time, then schedule."
            : "Ask Social Hood's time no longer fits the reply window. Pick another."}
        </p>
      ) : null}
      {closesAt ? (
        <p className="text-xs text-fg-secondary">Window closes {formatDayTime(closesAt, timeZone, now)}</p>
      ) : null}
      {windowTooShort ? (
        <p className="text-sm text-warning">The reply window closes too soon to schedule. Reply now instead.</p>
      ) : (
        <>
          <ScheduleFields
            idPrefix={`schedule-${conversation.id}`}
            value={value}
            onChange={(next) => {
              setValue(next);
              setError(null);
              setLimitError(null);
            }}
            timeZone={timeZone}
            limits={limits}
            error={error}
          />
          {error ? <UpgradeAction error={limitError} /> : null}
          {hasText ? null : <p className="text-xs text-fg-secondary">Write a message first.</p>}
          <Button
            className="w-full bg-brand-gradient text-white"
            disabled={!hasText || blocked || create.isPending}
            onClick={schedule}
          >
            {create.isPending ? "Scheduling…" : "Schedule"}
          </Button>
        </>
      )}
    </div>
  );
}

/** The composer's uploads; this component state resets with the conversation (keyed thread). */
function useAttachmentTray(wid: string, injected?: Uploader) {
  const api = useApi();
  const [items, setItems] = useState<TrayItem[]>([]);
  const controllers = useRef(new Map<string, AbortController>());
  const itemsRef = useRef(items);
  useEffect(() => {
    itemsRef.current = items;
  });

  const upload: Uploader = useCallback(
    (file, options) => (injected ? injected(file, options) : uploadAsset(api, wid, file, options)),
    [api, injected, wid],
  );

  const patch = (id: string, change: Partial<TrayItem>) =>
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...change } : item)));

  const start = (id: string, file: File) => {
    const controller = new AbortController();
    controllers.current.set(id, controller);
    upload(file, { signal: controller.signal, onProgress: (progress) => patch(id, { progress }) })
      .then((asset) => patch(id, { status: "done", progress: 1, asset }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof UploadError ? error.message : errorMessage(error);
        patch(id, { status: "failed", error: message });
        toast.error(`${file.name}: ${message}`);
      })
      .finally(() => controllers.current.delete(id));
  };

  const add = (file: File) => {
    const id = uuid();
    let previewUrl: string | null = null;
    if (file.type.startsWith("image/")) {
      try {
        previewUrl = URL.createObjectURL(file);
      } catch {
        previewUrl = null; // no preview; the file icon shows instead
      }
    }
    setItems((current) => [...current, { id, file, previewUrl, progress: 0, status: "uploading" }]);
    start(id, file);
  };

  const release = (item: TrayItem) => {
    controllers.current.get(item.id)?.abort();
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  };

  const remove = (id: string) => {
    const item = itemsRef.current.find((i) => i.id === id);
    if (item) release(item);
    setItems((current) => current.filter((i) => i.id !== id));
  };

  const retry = (id: string) => {
    const item = itemsRef.current.find((i) => i.id === id);
    if (!item) return;
    patch(id, { status: "uploading", progress: 0, error: undefined });
    start(id, item.file);
  };

  /** After sending: the files went with the message; drop the previews without aborting. */
  const clear = () => {
    for (const item of itemsRef.current) if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    setItems([]);
  };

  useEffect(() => {
    const map = controllers.current;
    return () => {
      for (const controller of map.values()) controller.abort();
      for (const item of itemsRef.current) if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    };
  }, []);

  return { items, add, remove, retry, clear };
}

/** A WhatsApp sticker: check it, upload it, hand back the asset (or null after a toast). */
function useStickerUpload(wid: string, injected?: Uploader) {
  const api = useApi();
  const [busy, setBusy] = useState(false);
  const upload = useCallback(
    async (file: File): Promise<MediaAsset | null> => {
      const problem = STICKER_RULE.check(file);
      if (problem) {
        toast.error(problem);
        return null;
      }
      setBusy(true);
      const options = { onProgress: () => {}, signal: new AbortController().signal };
      try {
        return await (injected ? injected(file, options) : uploadAsset(api, wid, file, options));
      } catch (error) {
        toast.error(error instanceof UploadError ? error.message : errorMessage(error));
        return null;
      } finally {
        setBusy(false);
      }
    },
    [api, injected, wid],
  );
  return { busy, upload };
}
