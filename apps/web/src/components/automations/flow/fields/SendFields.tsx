"use client";

import { Plus, X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { FlowButton } from "@/lib/api/types";
import type { SendNode } from "@/lib/automations/flow";
import { formatCount } from "@/lib/automations/format";
import { messageLimit, messageSize } from "@/lib/automations/limits";
import { MAX_BUTTONS, MESSAGE_MAX_CHARS } from "@/lib/automations/render";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { ImageAttach, InsertFieldMenu, LinkButtons } from "../../steps/ThenStep";
import { useFlowEnv } from "../FlowContext";
import { NativeSelect } from "../NativeSelect";

/**
 * A Send step: the message, its image and its link buttons, with the builder's own parts (the
 * insert-field menu, the byte count, the image upload, the link button rows). Quick replies are
 * the step's branches and show below the fields (StepTree).
 */
export function SendFields({ node }: { node: SendNode }) {
  const env = useFlowEnv();
  const problems = env.problemsOf(node.id);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const size = messageSize(node.text, env.disclosure, env.platform);
  const { limit, unit } = messageLimit(env.platform);
  const over = size > limit;
  const textProblem = problems.text?.message;
  const imageProblem = problems.image_asset_id?.message;
  // A comment's first message is a private reply: text and link buttons only (C-030).
  const privateReply = env.comment && env.firstId === node.id;
  const hasReplies = node.replies.length > 0;

  const textId = `flow-${node.id}-text`;
  const link = node.buttons.flatMap((button, index) => (button.profile ? [] : [{ button, index }]));
  const profile = node.buttons.find((button) => button.profile);
  const linkErrors: Record<string, string> = {};
  link.forEach(({ index }, position) => {
    for (const part of ["title", "url"]) {
      const message = problems[`buttons.${index}.${part}`]?.message;
      if (message) linkErrors[`message_buttons.${position}.${part}`] = message;
    }
  });

  const set = (patch: Partial<SendNode>) =>
    env.patch(node.id, (current) => (current.kind === "send" ? { ...current, ...patch } : current));

  const setLink = (next: { title: string; url: string }[]) => {
    const rebuilt: FlowButton[] = next.map((button) => ({ title: button.title, url: button.url, profile: false }));
    env.patch(node.id, (current) =>
      current.kind === "send" ? { ...current, buttons: [...rebuilt, ...current.buttons.filter((b) => b.profile)] } : current,
    );
  };

  const chooseSource = (value: string) => {
    if (value === "saved" && !node.saved) {
      // A saved reply goes alone, so what a written message carried is dropped with the choice.
      set({ saved: true, saved_reply_id: node.saved_reply_id ?? null, image_asset_id: null, image_url: null, buttons: [] });
    } else if (value === "text" && node.saved) {
      set({ saved: false });
    }
  };
  const source = (
    <div className="space-y-1.5">
      <ToggleGroup aria-label="What to send" value={node.saved ? "saved" : "text"} onValueChange={chooseSource}>
        <ToggleGroupItem value="text">Write a message</ToggleGroupItem>
        <ToggleGroupItem value="saved" disabled={hasReplies}>
          Send a saved reply
        </ToggleGroupItem>
      </ToggleGroup>
      {hasReplies ? (
        <p className="text-xs text-fg-secondary">A saved reply goes alone. Remove the quick replies to use one.</p>
      ) : null}
    </div>
  );

  if (node.saved) {
    return (
      <div className="space-y-5">
        {source}
        <SavedReplyPicker node={node} onChange={(id) => set({ saved_reply_id: id })} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {source}
      <Field id={textId}>
        <div className="flex items-center justify-between gap-2">
          <FieldLabel>Message</FieldLabel>
          <InsertFieldMenu
            target={textarea}
            text={node.text}
            onChange={(text) => set({ text })}
            label={`Insert field in step ${env.numberOf(node.id)}`}
          />
        </div>
        <Textarea
          ref={textarea}
          id={textId}
          value={node.text}
          maxLength={MESSAGE_MAX_CHARS}
          rows={3}
          onChange={(event) => set({ text: event.target.value })}
          placeholder="Hi {first_name|there}! Here's the link you asked for."
          aria-invalid={over || textProblem ? true : undefined}
          aria-describedby={`${textId}-help${textProblem ? ` ${textId}-error` : ""}`}
        />
        <div className="flex items-start justify-between gap-3 text-xs">
          <p id={`${textId}-help`} className="text-fg-secondary">
            {"{first_name|there}"} becomes the person&apos;s first name, or &ldquo;there&rdquo;.
            {env.disclosure ? " The disclosure line is added at the end and counts toward the limit." : ""}
          </p>
          <p className={cn("shrink-0 tabular-nums", over ? "text-danger-fg" : "text-fg-secondary")}>
            {formatCount(size)} / {formatCount(limit)} {unit}
          </p>
        </div>
        {textProblem ? (
          <p id={`${textId}-error`} className="text-xs text-danger-fg">
            {textProblem}
          </p>
        ) : null}
      </Field>

      {privateReply && !node.image_asset_id ? (
        <p className="text-xs text-fg-secondary">
          The first message answers a comment, so it is text and link buttons. To share an image, put it in a later
          message, after they tap a quick reply or answer a question.
        </p>
      ) : hasReplies && !node.image_asset_id ? (
        <p className="text-xs text-fg-secondary">Quick replies go on a text message. Put the image in the step before.</p>
      ) : (
        <div className="space-y-2">
          <ImageAttach
            wid={env.wid}
            assetId={node.image_asset_id}
            url={node.image_url ?? null}
            onChange={(asset) => set({ image_asset_id: asset?.id ?? null, image_url: asset?.secure_url ?? null })}
            upload={env.upload}
          />
          {imageProblem ? <p className="text-xs text-danger-fg">{imageProblem}</p> : null}
        </div>
      )}

      {hasReplies ? (
        <p className="text-xs text-fg-secondary">
          A message has link buttons or quick replies, not both. Remove the quick replies to add link buttons.
        </p>
      ) : (
        <>
          <LinkButtons
            buttons={link.map(({ button }) => ({ title: button.title, url: button.url ?? "" }))}
            onChange={setLink}
            errors={linkErrors}
          />
          {profile ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="rounded-lg border border-line bg-raised px-3 py-1 font-medium">{profile.title}</span>
              <span className="text-xs text-fg-secondary">opens your Instagram profile</span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Remove the profile button"
                onClick={() => set({ buttons: node.buttons.filter((b) => !b.profile) })}
              >
                <X aria-hidden />
              </Button>
            </div>
          ) : env.platform === "facebook" ? null : (
            // The profile button opens the account's Instagram profile; a Page has none (GR-29).
            <Button
              variant="ghost"
              size="sm"
              disabled={node.buttons.length >= MAX_BUTTONS}
              onClick={() => set({ buttons: [...node.buttons, { title: "View profile", profile: true }] })}
            >
              <Plus aria-hidden /> Add a button to your profile
            </Button>
          )}
        </>
      )}
    </div>
  );
}

function SavedReplyPicker({ node, onChange }: { node: SendNode; onChange: (id: string | null) => void }) {
  const env = useFlowEnv();
  const workspace = useCurrentWorkspace();
  const problem = env.problemsOf(node.id).saved_reply_id?.message;
  const replies = env.savedReplies ?? [];
  const chosen = replies.find((reply) => reply.id === node.saved_reply_id);
  const errorId = `flow-${node.id}-saved-error`;
  return (
    <div className="space-y-2">
      <NativeSelect
        label="Saved reply"
        value={node.saved_reply_id ?? ""}
        onChange={(value) => onChange(value || null)}
        invalid={Boolean(problem)}
        describedBy={problem ? errorId : undefined}
      >
        <option value="">Choose a saved reply</option>
        {replies.map((reply) => (
          <option key={reply.id} value={reply.id}>
            {reply.title}
          </option>
        ))}
        {node.saved_reply_id && env.savedReplies && !chosen ? <option value={node.saved_reply_id}>Deleted saved reply</option> : null}
      </NativeSelect>
      {problem ? (
        <p id={errorId} className="text-xs text-danger-fg">
          {problem}
        </p>
      ) : null}
      {chosen ? (
        <p className="rounded-lg border border-line bg-raised px-3 py-2 text-sm break-words whitespace-pre-wrap">{chosen.body}</p>
      ) : null}
      <p className="text-xs text-fg-secondary">
        {env.savedReplies && replies.length === 0 ? "You have no saved replies yet. " : ""}
        The reply is read when the step runs, so editing it changes what people get.{" "}
        <Link href={`/w/${workspace.slug}/settings/replies` as Route} className="underline">
          Manage saved replies
        </Link>
      </p>
    </div>
  );
}
