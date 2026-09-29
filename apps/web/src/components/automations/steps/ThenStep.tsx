"use client";

import { ArrowDown, ArrowUp, ChevronDown, ImagePlus, Loader2, Plus, Sparkles, X } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useApi } from "@/lib/api/provider";
import type { ActionName, AutomationDefinition, LinkButton, MediaAsset, Plan } from "@/lib/api/types";
import { buttonProblems, errorsFor, isCommentTrigger, type FieldErrors } from "@/lib/automations/definition";
import { formatCount } from "@/lib/automations/format";
import {
  AI_INSTRUCTIONS_MAX,
  BUTTON_TEXT_MAX_CHARS,
  BUTTON_TITLE_MAX,
  insertAt,
  INSERTABLE_FIELDS,
  MAX_BUTTONS,
  MAX_PUBLIC_REPLIES,
  MESSAGE_LIMIT_BYTES,
  MESSAGE_MAX_CHARS,
  PUBLIC_REPLY_MAX,
  worstCaseBytes,
  worstCaseChars,
} from "@/lib/automations/render";
import { ATTACHMENT_RULES, UploadError, uploadAsset } from "@/lib/media/upload";
import { cn } from "@/lib/utils";

import { StepCard, type StepState } from "../StepCard";
import { ProBadge } from "../TemplateGallery";

export type Uploader = (
  file: File,
  options: { onProgress: (fraction: number) => void; signal: AbortSignal },
) => Promise<MediaAsset>;

type Change = (patch: Partial<AutomationDefinition>) => void;

/**
 * UX-SCR-03 Then: public reply variations for comment triggers (FR-AUT-14), then the DM
 * builder (FR-AUT-13) or Reply with AI.
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
  const stepErrors = ["action", "message_text", "message_media_asset_id", "ai_instructions", "public_reply_texts"]
    .flatMap((field) => errorsFor(errors, field))
    .concat(errorsFor(errors, "message_buttons"));

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
            className="h-9 flex-1 bg-field"
          />
          <Button
            variant="ghost"
            size="icon"
            className="size-9"
            aria-label={`Move reply ${index + 1} up`}
            disabled={index === 0}
            onClick={() => move(index, index - 1)}
          >
            <ArrowUp aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-9"
            aria-label={`Move reply ${index + 1} down`}
            disabled={index === texts.length - 1}
            onClick={() => move(index, index + 1)}
          >
            <ArrowDown aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-9"
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

  const insert = (token: string) => {
    const el = textarea.current;
    const start = el?.selectionStart ?? text.length;
    const end = el?.selectionEnd ?? start;
    const result = insertAt(text, token, start, end);
    change({ message_text: result.text });
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(result.caret, result.caret);
    });
  };

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="automation-message">Message</Label>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                Insert field <ChevronDown aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-56 border-line bg-panel shadow-xl"
              onCloseAutoFocus={(event) => event.preventDefault()}
            >
              {INSERTABLE_FIELDS.map((field) => (
                <DropdownMenuItem key={field.token} onSelect={() => insert(field.token)}>
                  <span>{field.label}</span>
                  <code className="ml-auto text-xs text-fg-secondary">{field.token}</code>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
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

      {comment && !draft.message_media_asset_id ? (
        // A comment's DM is a private reply, which Instagram sends as text and buttons only.
        <p className="text-xs text-fg-secondary">
          Replies to comments are text and link buttons. To share an image, link to it with a button.
        </p>
      ) : (
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
      )}

      <LinkButtons
        buttons={draft.message_buttons ?? []}
        onChange={(buttons) => change({ message_buttons: buttons })}
        errors={errors}
      />
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
          <Loader2 className="size-4 animate-spin text-brand-fg" aria-hidden />
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
                className="h-9 bg-field"
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
                className="h-9 bg-field"
              />
              {shownUrlProblem ? (
                <p id={`automation-button-${index}-url-error`} className="text-xs text-danger-fg">
                  {shownUrlProblem}
                </p>
              ) : null}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-9 self-start sm:mt-5"
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
      <p id="automation-ai-note" className="text-xs text-fg-secondary">
        The AI answers from your knowledge base, so AI replies start working when Knowledge arrives in Social Hood.
        When it can&apos;t answer from what you&apos;ve taught it, it sends nothing and flags the conversation for you.
      </p>
    </div>
  );
}
