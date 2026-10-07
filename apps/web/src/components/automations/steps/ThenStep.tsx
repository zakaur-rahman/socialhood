"use client";

import { ArrowDown, ArrowUp, ChevronDown, ImagePlus, Plus, Sparkles, X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRef, useState, type ChangeEvent, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useApi } from "@/lib/api/provider";
import type { ActionName, AutomationDefinition, LinkButton, MediaAsset, Plan } from "@/lib/api/types";
import {
  buttonProblems,
  DEFAULT_FOLLOW_NUDGE,
  DEFAULT_OPENING_BUTTON,
  DEFAULT_OPENING_TEXT,
  errorsFor,
  followNudgeProblem,
  isCommentTrigger,
  openingProblems,
  tapFirstOn,
  usesTapFirst,
  type FieldErrors,
} from "@/lib/automations/definition";
import { formatCount } from "@/lib/automations/format";
import {
  AI_INSTRUCTIONS_MAX,
  BUTTON_TEXT_MAX_CHARS,
  BUTTON_TITLE_MAX,
  charCount,
  clampChars,
  FOLLOW_NUDGE_MAX,
  insertAt,
  INSERTABLE_FIELDS,
  MAX_BUTTONS,
  MAX_PUBLIC_REPLIES,
  MESSAGE_LIMIT_BYTES,
  MESSAGE_MAX_CHARS,
  OPENING_BUTTON_MAX,
  OPENING_MAX_CHARS,
  PUBLIC_REPLY_MAX,
  worstCaseBytes,
  worstCaseChars,
} from "@/lib/automations/render";
import { ATTACHMENT_RULES, UploadError, uploadAsset } from "@/lib/media/upload";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { StepCard, type StepState } from "../StepCard";
import { ProBadge } from "../TemplateGallery";

export type Uploader = (
  file: File,
  options: { onProgress: (fraction: number) => void; signal: AbortSignal },
) => Promise<MediaAsset>;

type Change = (patch: Partial<AutomationDefinition>) => void;

/** Element ids for aria-describedby, skipping the ones that don't apply. */
const ids = (...values: (string | false | null | undefined)[]) => values.filter(Boolean).join(" ");

/**
 * UX-SCR-03 Then: public reply variations for comment triggers (FR-AUT-14), then the DM
 * builder (FR-AUT-13) or Reply with AI. A message on a comment trigger can open with tap first
 * (FR-AUT-21); a message on either trigger can end with the follow nudge (FR-AUT-22).
 */
export function ThenStep({
  wid,
  draft,
  change,
  errors,
  state,
  plan,
  disclosure,
  mediaUrl,
  onMediaChange,
  upload,
}: {
  wid: string;
  draft: AutomationDefinition;
  change: Change;
  errors: FieldErrors;
  state: StepState;
  plan: Plan;
  disclosure: string | null;
  mediaUrl: string | null;
  onMediaChange: (url: string | null) => void;
  upload?: Uploader;
}) {
  const comment = isCommentTrigger(draft.trigger);
  const stepErrors = [
    "action",
    "confirm_first",
    "opening_text",
    "opening_button",
    "message_text",
    "message_media_asset_id",
    "ai_instructions",
    "public_reply_texts",
  ]
    .flatMap((field) => errorsFor(errors, field))
    .concat(errorsFor(errors, "message_buttons"))
    .concat(["follow_nudge", "follow_nudge_text"].flatMap((field) => errorsFor(errors, field)));

  return (
    <StepCard id="then" label="Then" state={state} errors={[...new Set(stepErrors)]}>
      <div className="space-y-6">
        {comment ? (
          <ReplyVariations texts={draft.public_reply_texts ?? []} onChange={(texts) => change({ public_reply_texts: texts })} />
        ) : null}

        <div className="space-y-2">
          <p id="automation-action-label" className="text-sm font-medium">
            {comment ? "Send a DM" : "Reply with"}
          </p>
          <ToggleGroup
            aria-labelledby="automation-action-label"
            value={draft.action ?? ""}
            onValueChange={(value) => change({ action: value as ActionName })}
            className="max-w-md"
          >
            <ToggleGroupItem value="send_message">A message</ToggleGroupItem>
            <ToggleGroupItem value="ai_reply">
              <Sparkles className="size-4" aria-hidden /> AI reply
              {plan === "free" ? <ProBadge /> : null}
            </ToggleGroupItem>
          </ToggleGroup>
          {!draft.action ? <p className="text-xs text-fg-secondary">Choose what to send.</p> : null}
        </div>

        {draft.action === "send_message" ? (
          <>
            {comment ? <TapFirst draft={draft} change={change} errors={errors} disclosure={disclosure} /> : null}
            <DmBuilder
              wid={wid}
              comment={comment}
              draft={draft}
              change={change}
              errors={errors}
              disclosure={disclosure}
              mediaUrl={mediaUrl}
              onMediaChange={onMediaChange}
              upload={upload}
            />
            <FollowNudge draft={draft} change={change} errors={errors} />
          </>
        ) : null}
        {draft.action === "ai_reply" ? <AiReplyFields draft={draft} change={change} plan={plan} errors={errors} /> : null}
      </div>
    </StepCard>
  );
}

// ---- public reply variations (FR-AUT-14)

function ReplyVariations({ texts, onChange }: { texts: string[]; onChange: (texts: string[]) => void }) {
  const focusNext = useRef<number | null>(null);

  const move = (from: number, to: number) => {
    const next = [...texts];
    const [text] = next.splice(from, 1);
    next.splice(to, 0, text);
    onChange(next);
    focusNext.current = to;
  };

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">
        Reply publicly{" "}
        <span className="font-normal text-fg-secondary">
          · optional, up to {MAX_PUBLIC_REPLIES}, one picked at random
        </span>
      </legend>
      {texts.map((text, index) => (
        <div key={index} className="flex items-center gap-1">
          <Input
            ref={(node) => {
              if (node && focusNext.current === index) {
                focusNext.current = null;
                node.focus();
              }
            }}
            aria-label={`Public reply ${index + 1}`}
            value={text}
            maxLength={PUBLIC_REPLY_MAX}
            onChange={(event) => onChange(texts.map((t, i) => (i === index ? event.target.value : t)))}
            placeholder="Sent you a DM, {first_name|there}!"
            size="lg"
            className="flex-1"
          />
          <Button
            variant="ghost"
            size="icon-lg"
            aria-label={`Move reply ${index + 1} up`}
            disabled={index === 0}
            onClick={() => move(index, index - 1)}
          >
            <ArrowUp aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            aria-label={`Move reply ${index + 1} down`}
            disabled={index === texts.length - 1}
            onClick={() => move(index, index + 1)}
          >
            <ArrowDown aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            aria-label={`Remove reply ${index + 1}`}
            onClick={() => onChange(texts.filter((_, i) => i !== index))}
          >
            <X aria-hidden />
          </Button>
        </div>
      ))}
      <Button
        variant="ghost"
        size="sm"
        disabled={texts.length >= MAX_PUBLIC_REPLIES}
        onClick={() => {
          focusNext.current = texts.length;
          onChange([...texts, ""]);
        }}
      >
        <Plus aria-hidden /> Add a public reply
      </Button>
    </fieldset>
  );
}

// ---- DM builder (FR-AUT-13)

function DmBuilder({
  wid,
  comment,
  draft,
  change,
  errors,
  disclosure,
  mediaUrl,
  onMediaChange,
  upload,
}: {
  wid: string;
  comment: boolean;
  draft: AutomationDefinition;
  change: Change;
  errors: FieldErrors;
  disclosure: string | null;
  mediaUrl: string | null;
  onMediaChange: (url: string | null) => void;
  upload?: Uploader;
}) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const text = draft.message_text ?? "";
  const bytes = worstCaseBytes(text, disclosure);
  const over = bytes > MESSAGE_LIMIT_BYTES;
  const buttons = draft.message_buttons ?? [];
  const overButtonText = buttons.length > 0 && worstCaseChars(text, disclosure) > BUTTON_TEXT_MAX_CHARS;
  const textError = errorsFor(errors, "message_text")[0];
  // Tap first's message is a normal DM, which can carry an image; a private reply can't (C-030).
  const tapFirst = usesTapFirst(draft);
  const imageAllowed = !comment || tapFirst;

  return (
    <div
      role={tapFirst ? "group" : undefined}
      aria-labelledby={tapFirst ? "automation-after-tap" : undefined}
      className="space-y-5"
    >
      {tapFirst ? (
        <div className="space-y-0.5">
          <p id="automation-after-tap" className="text-sm font-medium">
            Sent after they tap or reply
          </p>
          <p className="text-xs text-fg-secondary">
            A normal DM: their real first name, an image and link buttons all work.
          </p>
        </div>
      ) : null}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="automation-message">Message</Label>
          <InsertFieldMenu target={textarea} text={text} onChange={(next) => change({ message_text: next })} />
        </div>
        <Textarea
          ref={textarea}
          id="automation-message"
          value={text}
          maxLength={MESSAGE_MAX_CHARS}
          rows={4}
          onChange={(event) => change({ message_text: event.target.value })}
          placeholder="Hi {first_name|there}! Here's the link you asked for."
          aria-invalid={over || overButtonText || textError ? true : undefined}
          aria-describedby="automation-message-help automation-message-bytes"
        />
        <div className="flex items-start justify-between gap-3 text-xs">
          <p id="automation-message-help" className="text-fg-secondary">
            {"{first_name|there}"} becomes the person&apos;s first name, or &ldquo;there&rdquo; when it&apos;s unknown.
            {disclosure ? " The disclosure line is added at the end and counts toward the limit." : ""}
          </p>
          <p
            id="automation-message-bytes"
            className={cn("shrink-0 tabular-nums", over ? "text-danger-fg" : "text-fg-secondary")}
          >
            {formatCount(bytes)} / {formatCount(MESSAGE_LIMIT_BYTES)} bytes
          </p>
        </div>
        {over ? (
          <p className="text-xs text-danger-fg">
            Instagram allows {formatCount(MESSAGE_LIMIT_BYTES)} bytes in a DM, counting the longest name. Shorten the message.
          </p>
        ) : overButtonText ? (
          <p className="text-xs text-danger-fg">
            With link buttons Instagram allows {formatCount(BUTTON_TEXT_MAX_CHARS)} characters, counting the longest name.
            Shorten the message.
          </p>
        ) : null}
      </div>

      {!imageAllowed && !draft.message_media_asset_id ? (
        // A comment's DM is a private reply, which Instagram sends as text and buttons only.
        <p className="text-xs text-fg-secondary">
          Replies to comments are text and link buttons. To share an image, link to it with a button, or turn on Tap
          first.
        </p>
      ) : (
        <div className="space-y-2">
          <ImageAttach
            wid={wid}
            assetId={draft.message_media_asset_id ?? null}
            url={mediaUrl}
            onChange={(asset) => {
              change({ message_media_asset_id: asset?.id ?? null });
              onMediaChange(asset?.secure_url ?? null);
            }}
            upload={upload}
          />
          {!imageAllowed ? (
            <p className="text-xs text-danger-fg">
              Replies to comments can&apos;t carry an image. Turn on Tap first, or remove the image.
            </p>
          ) : null}
        </div>
      )}

      <LinkButtons
        buttons={draft.message_buttons ?? []}
        onChange={(buttons) => change({ message_buttons: buttons })}
        errors={errors}
      />
    </div>
  );
}

/** "Insert field" for a text area: puts {first_name|there} or {username} at the cursor. */
function InsertFieldMenu({
  target,
  text,
  onChange,
  label,
}: {
  target: RefObject<HTMLTextAreaElement | null>;
  text: string;
  onChange: (text: string) => void;
  /** An accessible name when two menus share a step; it starts with the visible "Insert field". */
  label?: string;
}) {
  const insert = (token: string) => {
    const el = target.current;
    const start = el?.selectionStart ?? text.length;
    const end = el?.selectionEnd ?? start;
    const result = insertAt(text, token, start, end);
    onChange(result.text);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(result.caret, result.caret);
    });
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" aria-label={label}>
          Insert field <ChevronDown aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onCloseAutoFocus={(event) => event.preventDefault()}>
        {INSERTABLE_FIELDS.map((field) => (
          <DropdownMenuItem key={field.token} onSelect={() => insert(field.token)}>
            <span>{field.label}</span>
            <code className="ml-auto text-xs text-fg-secondary">{field.token}</code>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ---- tap first (FR-AUT-21)

/**
 * Comment triggers: open with a short text and one quick-reply button, and send the message once
 * they tap it or reply. A private reply is one text-only message until they answer.
 */
function TapFirst({
  draft,
  change,
  errors,
  disclosure,
}: {
  draft: AutomationDefinition;
  change: Change;
  errors: FieldErrors;
  disclosure: string | null;
}) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const on = draft.confirm_first;
  const text = draft.opening_text ?? "";
  const button = draft.opening_button ?? "";
  const bytes = worstCaseBytes(text, disclosure);
  const problems = openingProblems(draft, disclosure);
  const textProblem = errorsFor(errors, "opening_text")[0] ?? problems.text;
  const buttonProblem = errorsFor(errors, "opening_button")[0] ?? problems.button;

  return (
    <div className="space-y-4 rounded-lg border border-line p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="automation-tap-first">
            Tap first{" "}
            <span className="rounded-full bg-brand-soft px-2 py-0.5 text-2xs font-semibold text-brand-fg">
              Recommended
            </span>
          </Label>
          <p id="automation-tap-first-hint" className="text-xs text-fg-secondary">
            Instagram allows one text-only reply to a comment until the person answers. Once they tap the button or
            reply, your message can use their real first name, an image and link buttons, and you can follow up.
          </p>
        </div>
        <Switch
          id="automation-tap-first"
          checked={on}
          onCheckedChange={(checked) => change(checked ? tapFirstOn(draft) : { confirm_first: false })}
          aria-describedby="automation-tap-first-hint"
          className="mt-0.5"
        />
      </div>

      {on ? (
        <>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="automation-opening">Opening message</Label>
              <InsertFieldMenu
                target={textarea}
                text={text}
                onChange={(next) => change({ opening_text: next })}
                label="Insert field in the opening message"
              />
            </div>
            <Textarea
              ref={textarea}
              id="automation-opening"
              value={text}
              maxLength={OPENING_MAX_CHARS}
              rows={3}
              onChange={(event) => change({ opening_text: event.target.value })}
              placeholder={DEFAULT_OPENING_TEXT}
              aria-invalid={textProblem ? true : undefined}
              aria-describedby={ids(
                "automation-opening-help",
                "automation-opening-bytes",
                textProblem && "automation-opening-error",
              )}
            />
            <div className="flex items-start justify-between gap-3 text-xs">
              <p id="automation-opening-help" className="text-fg-secondary">
                The reply to their comment, sent as text with the button below.
                {disclosure ? " The disclosure line is added at the end and counts toward the limit." : ""}
              </p>
              <p
                id="automation-opening-bytes"
                className={cn(
                  "shrink-0 tabular-nums",
                  bytes > MESSAGE_LIMIT_BYTES ? "text-danger-fg" : "text-fg-secondary",
                )}
              >
                {formatCount(bytes)} / {formatCount(MESSAGE_LIMIT_BYTES)} bytes
              </p>
            </div>
            {textProblem ? (
              <p id="automation-opening-error" className="text-xs text-danger-fg">
                {textProblem}
              </p>
            ) : null}
          </div>

          <div className="space-y-1">
            <Label htmlFor="automation-opening-button">Button title</Label>
            <Input
              id="automation-opening-button"
              value={button}
              onChange={(event) => change({ opening_button: clampChars(event.target.value, OPENING_BUTTON_MAX) })}
              placeholder={DEFAULT_OPENING_BUTTON}
              aria-invalid={buttonProblem ? true : undefined}
              aria-describedby="automation-opening-button-count"
              size="lg"
              className="sm:max-w-xs"
            />
            <p
              id="automation-opening-button-count"
              className={cn("text-xs tabular-nums", buttonProblem ? "text-danger-fg" : "text-fg-secondary")}
            >
              {buttonProblem ?? `${charCount(button)} / ${OPENING_BUTTON_MAX}`}
            </p>
          </div>
        </>
      ) : null}
    </div>
  );
}

// ---- follow nudge (FR-AUT-22)

/**
 * One more message after the automation's, only to people Instagram reports as not following the
 * account. Never a gate: the message goes to everyone either way.
 */
function FollowNudge({ draft, change, errors }: { draft: AutomationDefinition; change: Change; errors: FieldErrors }) {
  const on = draft.follow_nudge;
  const text = draft.follow_nudge_text ?? "";
  const problem = errorsFor(errors, "follow_nudge_text")[0] ?? (on ? followNudgeProblem(text) : null);

  return (
    <div className="space-y-4 rounded-lg border border-line p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="automation-follow-nudge" className="leading-snug">
            Suggest following to people who don&apos;t follow you yet
          </Label>
          <p id="automation-follow-nudge-note" className="text-xs text-fg-secondary">
            Sent after your message, only to people who don&apos;t follow you. Your message is never held back:
            Instagram&apos;s rules don&apos;t allow asking for a follow or a share in exchange for content.
          </p>
        </div>
        <Switch
          id="automation-follow-nudge"
          checked={on}
          onCheckedChange={(checked) =>
            change(
              checked
                ? { follow_nudge: true, follow_nudge_text: text.trim() ? text : DEFAULT_FOLLOW_NUDGE }
                : { follow_nudge: false },
            )
          }
          aria-describedby="automation-follow-nudge-note"
          className="mt-0.5"
        />
      </div>

      {on ? (
        <div className="space-y-2">
          <Label htmlFor="automation-follow-nudge-text">Follow message</Label>
          <Textarea
            id="automation-follow-nudge-text"
            value={text}
            rows={2}
            onChange={(event) => change({ follow_nudge_text: clampChars(event.target.value, FOLLOW_NUDGE_MAX) })}
            placeholder={DEFAULT_FOLLOW_NUDGE}
            aria-invalid={problem ? true : undefined}
            aria-describedby={ids("automation-follow-nudge-count", problem && "automation-follow-nudge-error")}
          />
          <div className="flex items-start justify-between gap-3 text-xs">
            <p id="automation-follow-nudge-error" className="text-danger-fg">
              {problem ?? ""}
            </p>
            <p id="automation-follow-nudge-count" className="shrink-0 text-fg-secondary tabular-nums">
              {charCount(text)} / {FOLLOW_NUDGE_MAX}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-fg-secondary">
            <span>Sent with a button to your profile:</span>
            <span
              data-testid="nudge-button-preview"
              className="inline-flex h-8 items-center rounded-lg border border-line bg-raised px-4 font-medium text-fg"
            >
              View profile
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

const IMAGE_ACCEPT = ".jpg,.jpeg,.png,.webp,.heic";

function ImageAttach({
  wid,
  assetId,
  url,
  onChange,
  upload,
}: {
  wid: string;
  assetId: string | null;
  url: string | null;
  onChange: (asset: MediaAsset | null) => void;
  upload?: Uploader;
}) {
  const api = useApi();
  const input = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const pick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const check = ATTACHMENT_RULES.instagram.check(file);
    if (check || !file.type.startsWith("image/")) {
      setProblem(check ?? "Choose a JPEG, PNG or WebP image.");
      return;
    }
    setProblem(null);
    setProgress(0);
    const abort = new AbortController();
    controller.current = abort;
    const options = { onProgress: (fraction: number) => setProgress(fraction), signal: abort.signal };
    try {
      const asset = await (upload ? upload(file, options) : uploadAsset(api, wid, file, options));
      onChange(asset);
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setProblem(error instanceof UploadError ? error.message : "The upload didn't finish. Try again.");
      }
    } finally {
      setProgress(null);
      controller.current = null;
    }
  };

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">
        Image <span className="font-normal text-fg-secondary">· optional, sent before the text</span>
      </p>
      {progress !== null ? (
        <div className="flex items-center gap-3 rounded-lg border border-line bg-field p-3 text-sm">
          <Spinner className="text-brand-fg" />
          <span className="tabular-nums" role="status">
            Uploading {Math.round(progress * 100)}%
          </span>
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => controller.current?.abort()}>
            Cancel
          </Button>
        </div>
      ) : assetId ? (
        <div className="flex items-center gap-3">
          {url ? (
            // eslint-disable-next-line @next/next/no-img-element -- a storage URL of any size
            <img src={url} alt="Image sent with the message" className="size-16 rounded-lg object-cover" />
          ) : (
            <span className="grid size-16 place-items-center rounded-lg bg-raised text-xs text-fg-secondary">Image</span>
          )}
          <Button variant="ghost" size="sm" onClick={() => onChange(null)}>
            <X aria-hidden /> Remove image
          </Button>
        </div>
      ) : (
        <Button variant="secondary" size="sm" onClick={() => input.current?.click()}>
          <ImagePlus aria-hidden /> Add an image
        </Button>
      )}
      <input
        ref={input}
        type="file"
        accept={IMAGE_ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose an image"
        onChange={(event) => void pick(event)}
      />
      {problem ? (
        <p role="alert" className="text-xs text-danger-fg">
          {problem}
        </p>
      ) : null}
    </div>
  );
}

function LinkButtons({
  buttons,
  onChange,
  errors,
}: {
  buttons: LinkButton[];
  onChange: (buttons: LinkButton[]) => void;
  errors: FieldErrors;
}) {
  const edit = (index: number, patch: Partial<LinkButton>) =>
    onChange(buttons.map((button, i) => (i === index ? { ...button, ...patch } : button)));

  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium">
        Link buttons{" "}
        <span className="font-normal text-fg-secondary tabular-nums">
          · {buttons.length} of {MAX_BUTTONS}
        </span>
      </legend>
      {buttons.map((button, index) => {
        const problems = buttonProblems(button);
        // As you type: a URL is checked once there is one; a title once the URL is filled in.
        const serverTitle = errors[`message_buttons.${index}.title`];
        const serverUrl = errors[`message_buttons.${index}.url`];
        const titleProblem = serverTitle ?? (button.url.trim() ? problems.title : undefined);
        const shownUrlProblem = serverUrl ?? (button.url.trim() ? problems.url : undefined);
        return (
          <div key={index} className="grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
            <div className="space-y-1">
              <Label htmlFor={`automation-button-${index}-title`} className="text-xs text-fg-secondary">
                Button {index + 1} title
              </Label>
              <Input
                id={`automation-button-${index}-title`}
                value={button.title}
                maxLength={BUTTON_TITLE_MAX}
                onChange={(event) => edit(index, { title: event.target.value })}
                placeholder="Shop now"
                aria-invalid={titleProblem ? true : undefined}
                size="lg"
              />
              <p className={cn("text-xs tabular-nums", titleProblem ? "text-danger-fg" : "text-fg-secondary")}>
                {titleProblem ?? `${button.title.length} / ${BUTTON_TITLE_MAX}`}
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor={`automation-button-${index}-url`} className="text-xs text-fg-secondary">
                Button {index + 1} link
              </Label>
              <Input
                id={`automation-button-${index}-url`}
                type="url"
                inputMode="url"
                value={button.url}
                maxLength={2000}
                onChange={(event) => edit(index, { url: event.target.value })}
                placeholder="https://"
                aria-invalid={shownUrlProblem ? true : undefined}
                aria-describedby={shownUrlProblem ? `automation-button-${index}-url-error` : undefined}
                size="lg"
              />
              {shownUrlProblem ? (
                <p id={`automation-button-${index}-url-error`} className="text-xs text-danger-fg">
                  {shownUrlProblem}
                </p>
              ) : null}
            </div>
            <Button
              variant="ghost"
              size="icon-lg"
              className="self-start sm:mt-5"
              aria-label={`Remove button ${index + 1}`}
              onClick={() => onChange(buttons.filter((_, i) => i !== index))}
            >
              <X aria-hidden />
            </Button>
          </div>
        );
      })}
      <Button
        variant="ghost"
        size="sm"
        disabled={buttons.length >= MAX_BUTTONS}
        onClick={() => onChange([...buttons, { title: "", url: "" }])}
      >
        <Plus aria-hidden /> Add a link button
      </Button>
    </fieldset>
  );
}

// ---- Reply with AI

function AiReplyFields({
  draft,
  change,
  plan,
  errors,
}: {
  draft: AutomationDefinition;
  change: Change;
  plan: Plan;
  errors: FieldErrors;
}) {
  const text = draft.ai_instructions ?? "";
  const error = errorsFor(errors, "ai_instructions")[0];
  const workspace = useCurrentWorkspace();
  // Knowledge is for owners and admins (agents don't see Grow).
  const canManageKnowledge = workspace.role !== "agent";
  return (
    <div className="space-y-3">
      {plan === "free" ? (
        <p className="flex items-center gap-2 rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand-fg">
          <ProBadge /> Replies with AI are part of Pro. Set it up now and activate it after upgrading.
        </p>
      ) : null}
      <div className="space-y-2">
        <Label htmlFor="automation-ai">Instructions</Label>
        <Textarea
          id="automation-ai"
          value={text}
          maxLength={AI_INSTRUCTIONS_MAX}
          rows={4}
          onChange={(event) => change({ ai_instructions: event.target.value })}
          placeholder="Answer price questions from the catalogue. Keep it to two sentences and link the shop."
          aria-invalid={error ? true : undefined}
          aria-describedby="automation-ai-count automation-ai-note"
        />
        <p id="automation-ai-count" className="text-right text-xs text-fg-secondary tabular-nums">
          {formatCount(text.length)} / {formatCount(AI_INSTRUCTIONS_MAX)}
        </p>
      </div>
      <p className="text-xs text-fg-secondary">
        {/* The sentence alone describes the field; the link is its own stop. */}
        <span id="automation-ai-note">
          The AI answers from your knowledge. When the answer isn&apos;t there, it sends nothing and moves the
          conversation to Needs you.
        </span>
        {canManageKnowledge ? (
          <>
            {" "}
            {/* Underlined at rest: in a line of text, colour alone doesn't mark a link (WCAG 1.4.1). */}
            <Link href={`/w/${workspace.slug}/knowledge` as Route} className="text-brand-fg underline underline-offset-4">
              Open Knowledge
            </Link>
          </>
        ) : null}
      </p>
    </div>
  );
}
