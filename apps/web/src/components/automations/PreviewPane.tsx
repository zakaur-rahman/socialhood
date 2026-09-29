"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition } from "@/lib/api/types";
import { isCommentTrigger } from "@/lib/automations/definition";
import { renderFields, withDisclosure, type FieldValues } from "@/lib/automations/render";

export const SAMPLE_CONTACT = { first_name: "Priya", username: "priya.styles" } as const;

type Sample = "known" | "unknown";

const SAMPLES: Record<Sample, FieldValues> = {
  known: SAMPLE_CONTACT,
  unknown: { first_name: null, username: SAMPLE_CONTACT.username },
};

/**
 * UX-SCR-03 Preview: an Instagram-style comment, public reply and DM with its buttons, rendered
 * as you type for a sample contact, or for one whose name is unknown (the fallback shows).
 */
export function PreviewPane({
  draft,
  accountUsername,
  disclosure,
  mediaUrl,
}: {
  draft: AutomationDefinition;
  accountUsername: string | null;
  disclosure: string | null;
  mediaUrl: string | null;
}) {
  const [sample, setSample] = useState<Sample>("known");
  const values = SAMPLES[sample];
  const comment = isCommentTrigger(draft.trigger);
  const keyword = draft.trigger === "comment_any" ? null : (draft.keywords?.[0] ?? null);
  const incoming = keyword ? keyword.toUpperCase() : comment ? "Love this!" : "Hi";
  const replies = (draft.public_reply_texts ?? []).map((text) => text.trim()).filter(Boolean);
  const reply = replies[0] ? renderFields(replies[0], values) : null;
  const text = draft.message_text?.trim() ? renderFields(draft.message_text, values) : "";
  // The disclosure line (FR-AUT-11) ends every automated DM.
  const body = text ? withDisclosure(text, disclosure) : (disclosure ?? "");
  const buttons = (draft.message_buttons ?? []).filter((button) => button.title.trim());
  const me = accountUsername ?? "your.account";

  return (
    <div className="space-y-3">
      <ToggleGroup aria-label="Sample contact" value={sample} onValueChange={(value) => setSample(value as Sample)}>
        <ToggleGroupItem value="known">{SAMPLE_CONTACT.first_name}</ToggleGroupItem>
        <ToggleGroupItem value="unknown">Name unknown</ToggleGroupItem>
      </ToggleGroup>

      <div data-testid="preview" className="space-y-3 rounded-2xl border border-line bg-canvas p-3 text-sm">
        {comment ? (
          <>
            <div className="flex gap-2">
              <span aria-hidden className="bg-brand-gradient-decor size-6 shrink-0 rounded-full" />
              <p className="min-w-0 leading-snug">
                <span className="font-semibold">{SAMPLE_CONTACT.username}</span> {incoming}
                <span className="block text-[11px] text-fg-secondary">2m · Reply</span>
              </p>
            </div>
            {reply ? (
              <div className="ml-8 flex gap-2">
                <span aria-hidden className="bg-shell-gradient size-6 shrink-0 rounded-full" />
                <p className="min-w-0 leading-snug break-words">
                  <span className="font-semibold">{me}</span> {reply}
                  <span className="block text-[11px] text-fg-secondary">
                    now{replies.length > 1 ? ` · 1 of ${replies.length} replies, picked at random` : ""}
                  </span>
                </p>
              </div>
            ) : null}
            <p className="text-center text-[11px] text-fg-secondary">Direct message</p>
          </>
        ) : (
          <div className="flex justify-start">
            <p className="max-w-[85%] rounded-2xl rounded-bl-md bg-field px-3 py-2 shadow-sm">{incoming}</p>
          </div>
        )}

        <div className="flex justify-end">
          {draft.action === "ai_reply" ? (
            <p className="bg-brand-gradient flex max-w-[88%] items-start gap-2 rounded-2xl rounded-br-md px-3 py-2 text-white">
              <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
              The AI writes a reply from your knowledge base.
            </p>
          ) : draft.action === "send_message" && (text || mediaUrl || buttons.length > 0) ? (
            <div className="bg-brand-gradient max-w-[88%] space-y-2 rounded-2xl rounded-br-md px-3 py-2 text-white">
              {mediaUrl ? (
                // eslint-disable-next-line @next/next/no-img-element -- a storage URL of any size
                <img src={mediaUrl} alt="" className="max-h-40 w-full rounded-lg object-cover" />
              ) : null}
              {body ? (
                <p data-testid="preview-message" className="leading-relaxed break-words whitespace-pre-wrap">
                  {body}
                </p>
              ) : null}
              {buttons.map((button, index) => (
                <span key={index} className="block rounded-lg bg-white/15 py-1.5 text-center text-xs font-medium">
                  {button.title}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-fg-secondary">Write the message in Then to see it here.</p>
          )}
        </div>
      </div>
    </div>
  );
}
