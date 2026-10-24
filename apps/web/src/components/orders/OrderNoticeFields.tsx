"use client";

import { useMemo } from "react";

import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useWhatsAppTemplates } from "@/lib/api/queries";
import type { Order, OrderNotice, OrderNoticeInput } from "@/lib/api/types";
import { useCurrentWorkspace } from "@/lib/workspace";

import { NativeSelect } from "../automations/flow/NativeSelect";

export type NoticeState = { on: boolean; message: string; template: string };

export const NO_NOTICE: NoticeState = { on: false, message: "", template: "" };

/** The request's `notice`, or null when the member didn't ask for a message. */
export function noticeOf(state: NoticeState): OrderNoticeInput | null {
  if (!state.on) return null;
  const [name, language] = state.template ? state.template.split("|") : [null, null];
  return {
    message: state.message.trim() || null,
    template_name: name,
    template_language: language,
  };
}

/** What happened to the message that was asked for, in one plain sentence (null: none was asked for). */
export function noticeSentence(notice: OrderNotice | null | undefined): string | null {
  if (!notice) return null;
  return notice.sent ? "The customer was messaged." : `The customer wasn't messaged. ${notice.reason ?? ""}`.trim();
}

/**
 * "Tell the customer" for a status change (GR-32): a switch, an optional message of your own (the
 * default wording otherwise), and, for a WhatsApp conversation, an approved utility template to
 * use when the 24-hour window has closed. Without a template the server says it can't be sent and
 * why; the order is changed either way.
 */
export function OrderNoticeFields({
  order,
  value,
  onChange,
}: {
  order: Pick<Order, "platform" | "social_account_id">;
  value: NoticeState;
  onChange: (next: NoticeState) => void;
}) {
  const { id: wid } = useCurrentWorkspace();
  const whatsapp = order.platform === "whatsapp" && Boolean(order.social_account_id);
  const templates = useWhatsAppTemplates(wid, order.social_account_id ?? "", whatsapp && value.on);
  const utility = useMemo(
    () => (templates.data ?? []).filter((t) => t.category === "utility" && t.status === "approved" && t.param_count <= 4),
    [templates.data],
  );
  return (
    <div className="space-y-2">
      <label className="flex items-center justify-between gap-3 text-sm">
        <span>Tell the customer in the chat</span>
        <Switch
          checked={value.on}
          onCheckedChange={(on) => onChange({ ...value, on })}
          aria-label="Tell the customer in the chat"
        />
      </label>
      {value.on ? (
        <div className="space-y-2">
          <Textarea
            rows={2}
            maxLength={500}
            value={value.message}
            onChange={(event) => onChange({ ...value, message: event.target.value })}
            placeholder="Leave blank to send the standard wording"
            aria-label="Message to the customer"
          />
          {whatsapp ? (
            <>
              <NativeSelect
                label="Template if the 24-hour window has closed"
                value={value.template}
                onChange={(template) => onChange({ ...value, template })}
              >
                <option value="">{templates.isPending ? "Loading templates" : "No template"}</option>
                {utility.map((t) => (
                  <option key={`${t.name}|${t.language}`} value={`${t.name}|${t.language}`}>
                    {t.name} ({t.language})
                  </option>
                ))}
              </NativeSelect>
              <p className="text-xs text-fg-secondary">
                After 24 hours WhatsApp only allows an approved utility template. It is filled with the customer&rsquo;s
                first name, the order number, the total and the status. Without one, the message isn&rsquo;t sent.
              </p>
            </>
          ) : (
            <p className="text-xs text-fg-secondary">
              It goes while the messaging window is open. Instagram and Messenger only allow messages for 24 hours after
              the customer writes.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
