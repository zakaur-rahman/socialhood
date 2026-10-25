"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applyMessage } from "@/lib/inbox/cache";

import { INLINE_PLAN_LIMITS, useApi } from "../provider";
import type { Message, ProductMessageSend, WaCatalogueConnectInput, WaCatalogueStatus } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** While a sync runs, the card refreshes this often. */
export const WA_CATALOGUE_POLL_MS = 4_000;

/**
 * The WhatsApp catalogue (GR-33): the connection to a Meta commerce catalogue and how its sync is
 * going. Reading is on every plan; connecting and syncing are part of Pro (PD-8).
 */
export function useWaCatalogue(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<WaCatalogueStatus>({
    queryKey: keys.waCatalogue(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/integrations/whatsapp-catalogue", { params: { path: { wid } } })),
    refetchInterval: (query) => (query.state.data?.syncing ? WA_CATALOGUE_POLL_MS : false),
  });
}

/** 402 on Free; 409 with Meta's reason in plain words when it won't show the catalogue. */
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

export function useSyncWaCatalogue(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<WaCatalogueStatus, Error, void>({
    mutationFn: () =>
      unwrap(api.POST("/v1/w/{wid}/integrations/whatsapp-catalogue/sync", { params: { path: { wid } } })),
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
    onSuccess: (message) => applyMessage(queryClient, wid, conversationId, message),
    meta: INLINE_PLAN_LIMITS,
  });
}
