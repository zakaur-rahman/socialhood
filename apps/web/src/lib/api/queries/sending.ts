"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { applyMessage } from "@/lib/inbox/cache";
import { useInboxStore } from "@/lib/inbox/store";
import { uuid } from "@/lib/uuid";

import { toApiError } from "../errors";
import { useApi } from "../provider";
import type { Attachment, MediaAsset, Message, MessageKind, SendMessage, TemplateSend } from "../types";
import { unwrap } from "./unwrap";

export type ReplyInput = {
  text?: string;
  assets?: MediaAsset[];
  /** WhatsApp outside the window (FR-INB-10), with the body as the customer will read it. */
  template?: TemplateSend & { preview: string };
  /** Instagram's heart sticker, sent on its own. */
  heart?: boolean;
  /** A WhatsApp sticker: an uploaded 512 x 512 WebP, sent on its own. */
  sticker?: MediaAsset;
  humanAgent?: boolean;
};

export const HEART = "\u2764\ufe0f";

function assetType(asset: MediaAsset): "image" | "video" | "audio" | "file" {
  if (asset.resource_type === "image") return "image";
  if (asset.resource_type === "video") return asset.mime_type?.startsWith("audio/") ? "audio" : "video";
  return "file";
}

function attachmentFor(asset: MediaAsset, asSticker = false): Attachment {
  return {
    id: asset.id,
    type: asSticker ? "sticker" : assetType(asset),
    url: asset.secure_url ?? "",
    filename: asset.original_filename ?? null,
    size_bytes: asset.bytes,
    width: asset.width ?? null,
    height: asset.height ?? null,
    duration_s: asset.duration_s ?? null,
  };
}

function kindFor(input: ReplyInput): MessageKind {
  if (input.template) return "template";
  if (input.heart || input.sticker) return "sticker";
  // As the API decides: attachments without text take the first attachment's kind.
  const first = input.assets?.[0];
  return first && !input.text?.trim() ? assetType(first) : "text";
}

/** The optimistic bubble (status queued) shown until the server's message replaces it. */
export function optimisticMessage(conversationId: string, clientId: string, input: ReplyInput): Message {
  return {
    id: `local-${clientId}`,
    conversation_id: conversationId,
    client_id: clientId,
    direction: "outbound",
    source: "human",
    kind: kindFor(input),
    text: input.heart ? HEART : input.template ? input.template.preview : input.text?.trim() || null,
    attachments: input.sticker
      ? [attachmentFor(input.sticker, true)]
      : (input.assets ?? []).map((asset) => attachmentFor(asset)),
    template: input.template
      ? { name: input.template.name, language: input.template.language, params: input.template.params ?? [] }
      : null,
    status: "queued",
    error: null,
    occurred_at: new Date().toISOString(),
    sent_at: null,
    delivered_at: null,
    read_at: null,
    sent_by: null,
    automation: null,
    suggestion_id: null,
    human_agent_tag: Boolean(input.humanAgent),
    reactions: [],
  };
}

export function isLocalMessage(message: Message): boolean {
  return message.id.startsWith("local-");
}

/**
 * Optimistic send (TR-FE-05, F-07). client_id is also the Idempotency-Key, and Retry of a send
 * that never reached the API resends the same body with the same key, so one click is never two
 * messages. message.created / message.updated (or the 202 response) replace the bubble.
 */
export function useSendReply(wid: string, conversationId: string) {
  const api = useApi();
  const queryClient = useQueryClient();

  const deliver = useCallback(
    async (clientId: string) => {
      const store = useInboxStore.getState();
      const entry = store.outbox[clientId];
      if (!entry) return;
      store.patchOutbox(clientId, { status: "queued", error: null });
      try {
        const message = await unwrap(
          api.POST("/v1/w/{wid}/conversations/{conversation_id}/messages", {
            params: {
              path: { wid, conversation_id: entry.conversationId },
              header: { "Idempotency-Key": clientId },
            },
            body: entry.body,
          }),
        );
        applyMessage(queryClient, wid, entry.conversationId, message);
        useInboxStore.getState().removeOutbox(clientId);
      } catch (error) {
        const apiError = toApiError(error);
        useInboxStore.getState().patchOutbox(clientId, {
          status: "failed",
          error: {
            code: apiError.code,
            // "internal" shows the request id; everything else shows the API's reason, which for a
            // validation error is the first field's message.
            message:
              apiError.code === "internal"
                ? (apiError.requestId ?? "")
                : (apiError.detail ?? apiError.errors[0]?.message ?? ""),
          },
        });
      }
    },
    [api, queryClient, wid],
  );

  const send = useCallback(
    (input: ReplyInput) => {
      const clientId = uuid();
      const sticker = Boolean(input.heart || input.sticker);
      const body: SendMessage = {
        client_id: clientId,
        text: input.template || sticker ? null : input.text?.trim() || null,
        attachment_asset_ids: sticker ? [] : (input.assets ?? []).map((asset) => asset.id),
        template: input.template
          ? { name: input.template.name, language: input.template.language, params: input.template.params ?? [] }
          : null,
        sticker: input.heart ? "like_heart" : null,
        sticker_asset_id: input.sticker?.id ?? null,
      };
      useInboxStore.getState().putOutbox({
        clientId,
        conversationId,
        body,
        message: optimisticMessage(conversationId, clientId, input),
      });
      void deliver(clientId);
      return clientId;
    },
    [conversationId, deliver],
  );

  /** Retry a failed bubble: resend a local one, or ask the API to retry a stored one. */
  const retry = useCallback(
    async (message: Message) => {
      if (isLocalMessage(message) && message.client_id) {
        await deliver(message.client_id);
        return;
      }
      applyMessage(queryClient, wid, conversationId, { ...message, status: "queued", error: null });
      try {
        const updated = await unwrap(
          api.POST("/v1/w/{wid}/messages/{message_id}/retry", { params: { path: { wid, message_id: message.id } } }),
        );
        applyMessage(queryClient, wid, conversationId, updated);
      } catch (error) {
        const apiError = toApiError(error);
        applyMessage(queryClient, wid, conversationId, {
          ...message,
          status: "failed",
          error: { code: apiError.code, message: apiError.detail ?? message.error?.message ?? "" },
        });
      }
    },
    [api, conversationId, deliver, queryClient, wid],
  );

  const discard = useCallback((message: Message) => {
    if (message.client_id) useInboxStore.getState().removeOutbox(message.client_id);
  }, []);

  return { send, retry, discard };
}
