"use client";

import { Plus, X } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import type { FlowButton } from "@/lib/api/types";
import type { SendNode } from "@/lib/automations/flow";
import { formatCount } from "@/lib/automations/format";
import { MAX_BUTTONS, MESSAGE_LIMIT_BYTES, MESSAGE_MAX_CHARS, worstCaseBytes } from "@/lib/automations/render";
import { cn } from "@/lib/utils";

import { ImageAttach, InsertFieldMenu, LinkButtons } from "../../steps/ThenStep";
import { useFlowEnv } from "../FlowContext";

/**
 * A Send step: the message, its image and its link buttons, with the builder's own parts (the
 * insert-field menu, the byte count, the image upload, the link button rows). Quick replies are
 * the step's branches and show below the fields (StepTree).
 */
export function SendFields({ node }: { node: SendNode }) {
  const env = useFlowEnv();
  const problems = env.problemsOf(node.id);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const bytes = worstCaseBytes(node.text, env.disclosure);
  const over = bytes > MESSAGE_LIMIT_BYTES;
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

  return (
    <div className="space-y-5">
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
            {formatCount(bytes)} / {formatCount(MESSAGE_LIMIT_BYTES)} bytes
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
          ) : (
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
