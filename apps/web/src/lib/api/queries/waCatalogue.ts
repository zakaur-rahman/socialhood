"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applyQueuedResponse } from "@/lib/inbox/cache";

import { INLINE_PLAN_LIMITS, useApi } from "../provider";
import type { Message, ProductMessageSend, WaCatalogueConnectInput, WaCatalogueStatus } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/**
 * The WhatsApp catalogue (GR-33, C-215): the connection to a Meta commerce catalogue, its feed link
 * (owners and admins only) and how the products stand against Meta's last fetch of that feed.
 * Reading is on every plan; connecting is part of Creator and Business (PD-8).
 */
export function useWaCatalogue(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<WaCatalogueStatus>({
    queryKey: keys.waCatalogue(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/integrations/whatsapp-catalogue", { params: { path: { wid } } })),
  });
}

/** 402 on Free; 422 when the catalogue id isn't digits. Doesn't contact Meta. */
export function useConnectWaCatalogue(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<WaCatalogueStatus, Error, WaCatalogueConnectInput>({
    mutationFn: (body) =>
      unwrap(api.PUT("/v1/w/{wid}/integrations/whatsapp-catalogue", { params: { path: { wid } }, body })),
    onSuccess: (status) => queryClient.setQueryData(keys.waCatalogue(wid), status),
    meta: INLINE_PLAN_LIMITS,
  });
}

/** A new feed link; the old one stops working at once. */
export function useRenewWaCatalogueFeedLink(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<WaCatalogueStatus, Error, void>({
    mutationFn: () =>
      unwrap(api.POST("/v1/w/{wid}/integrations/whatsapp-catalogue/feed-link", { params: { path: { wid } } })),
    onSuccess: (status) => queryClient.setQueryData(keys.waCatalogue(wid), status),
  });
}

export function useDisconnectWaCatalogue(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () =>
      expectOk(api.DELETE("/v1/w/{wid}/integrations/whatsapp-catalogue", { params: { path: { wid } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.waCatalogue(wid) }),
  });
}

/** Send a product or product-list message in a WhatsApp conversation; the new message joins the thread. */
export function useSendProductMessage(wid: string, conversationId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Message, Error, ProductMessageSend>({
    mutationFn: (body) =>
      unwrap(
        api.POST("/v1/w/{wid}/conversations/{conversation_id}/product-message", {
          params: { path: { wid, conversation_id: conversationId } },
          body,
        }),
      ),
    onSuccess: (message) => applyQueuedResponse(queryClient, wid, conversationId, message),
    meta: INLINE_PLAN_LIMITS,
  });
}
