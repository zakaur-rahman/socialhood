"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type {
  WebhookDelivery,
  WebhookDeliveryList,
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointList,
  WebhookEndpointPatch,
  WebhookEndpointWithSecret,
  WebhookEventType,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** The delivery log shows this many at a time (GR-04). */
export const DELIVERIES_PAGE = 20;
/** While a delivery is pending, the log refreshes this often. */
export const DELIVERIES_POLL_MS = 5_000;

/** Every event an endpoint can subscribe to (GR-04). */
export function useWebhookEvents(wid: string) {
  const api = useApi();
  return useQuery<WebhookEventType[]>({
    queryKey: keys.webhookEvents(wid),
    staleTime: Infinity,
    queryFn: async () =>
      (await unwrap(api.GET("/v1/w/{wid}/webhook-events", { params: { path: { wid } } }))).items,
  });
}

export function useWebhookEndpoints(wid: string) {
  const api = useApi();
  return useQuery<WebhookEndpointList>({
    queryKey: keys.webhookEndpoints(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/webhook-endpoints", { params: { path: { wid } } })),
  });
}

/** An endpoint's latest deliveries, refreshed while one is still being tried. */
export function useWebhookDeliveries(wid: string, endpointId: string) {
  const api = useApi();
  return useQuery<WebhookDeliveryList>({
    queryKey: keys.webhookDeliveries(wid, endpointId),
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/webhook-endpoints/{endpoint_id}/deliveries", {
          params: { path: { wid, endpoint_id: endpointId }, query: { limit: DELIVERIES_PAGE } },
        }),
      ),
    refetchInterval: (query) =>
      query.state.data?.items.some((d) => d.status === "pending") ? DELIVERIES_POLL_MS : false,
  });
}

function useRefresh(wid: string) {
  const qc = useQueryClient();
  return (endpointId?: string) => {
    void qc.invalidateQueries({ queryKey: keys.webhookEndpoints(wid) });
    if (endpointId) void qc.invalidateQueries({ queryKey: keys.webhookDeliveries(wid, endpointId) });
  };
}

export function useCreateWebhookEndpoint(wid: string) {
  const api = useApi();
  const refresh = useRefresh(wid);
  return useMutation<WebhookEndpointWithSecret, Error, WebhookEndpointCreate>({
    mutationFn: (body) =>
      unwrap(api.POST("/v1/w/{wid}/webhook-endpoints", { params: { path: { wid } }, body })),
    onSuccess: () => refresh(),
  });
}

export function useUpdateWebhookEndpoint(wid: string) {
  const api = useApi();
  const refresh = useRefresh(wid);
  return useMutation<WebhookEndpoint, Error, { id: string; body: WebhookEndpointPatch }>({
    mutationFn: ({ id, body }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/webhook-endpoints/{endpoint_id}", {
          params: { path: { wid, endpoint_id: id } },
          body,
        }),
      ),
    onSuccess: (endpoint) => refresh(endpoint.id),
  });
}

export function useDeleteWebhookEndpoint(wid: string) {
  const api = useApi();
  const refresh = useRefresh(wid);
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/webhook-endpoints/{endpoint_id}", {
          params: { path: { wid, endpoint_id: id } },
        }),
      ),
    onSuccess: () => refresh(),
  });
}

export function useRotateWebhookSecret(wid: string) {
  const api = useApi();
  return useMutation<WebhookEndpointWithSecret, Error, string>({
    mutationFn: (id) =>
      unwrap(
        api.POST("/v1/w/{wid}/webhook-endpoints/{endpoint_id}/rotate-secret", {
          params: { path: { wid, endpoint_id: id } },
        }),
      ),
  });
}

export function useSendWebhookTest(wid: string) {
  const api = useApi();
  const refresh = useRefresh(wid);
  return useMutation<WebhookDelivery, Error, string>({
    mutationFn: (id) =>
      unwrap(
        api.POST("/v1/w/{wid}/webhook-endpoints/{endpoint_id}/test", {
          params: { path: { wid, endpoint_id: id } },
        }),
      ),
    onSuccess: (delivery) => refresh(delivery.endpoint_id),
  });
}

export function useReplayWebhookDelivery(wid: string) {
  const api = useApi();
  const refresh = useRefresh(wid);
  return useMutation<WebhookDelivery, Error, string>({
    mutationFn: (id) =>
      unwrap(
        api.POST("/v1/w/{wid}/webhook-deliveries/{delivery_id}/replay", {
          params: { path: { wid, delivery_id: id } },
        }),
      ),
    onSuccess: (delivery) => refresh(delivery.endpoint_id),
  });
}
