"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type {
  Broadcast,
  BroadcastAvailability,
  BroadcastCreate,
  BroadcastDraft,
  BroadcastList,
  BroadcastPreview,
  BroadcastRecipientList,
  BroadcastUpdate,
  RecipientStatus,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

export const RECIPIENT_PAGE = 25;

/**
 * Whether broadcasts exist at all (the BROADCASTS_ENABLED server setting, off until the legal check
 * of marketing consent), what the plan allows this month and Meta's rate card. A request that fails
 * (an agent, an older API) reads as "not available", so the web shows nothing.
 */
export function useBroadcastAvailability(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<BroadcastAvailability, Error>({
    queryKey: keys.broadcastAvailability(wid),
    enabled,
    staleTime: 60_000,
    retry: false,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/broadcasts/availability", { params: { path: { wid } } })),
  });
}

/** Newest first, each with its counts. Polls while any broadcast is on its way. */
export function useBroadcasts(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<BroadcastList, Error>({
    queryKey: keys.broadcastLists(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/broadcasts", { params: { path: { wid }, query: { limit: 100 } } })),
    refetchInterval: (query) =>
      query.state.data?.items.some((b) => b.status === "sending" || b.status === "scheduled") ? 10_000 : false,
  });
}

/** One broadcast with its counts; polls every 5 s while it is sending so the statuses move. */
export function useBroadcast(wid: string, id: string) {
  const api = useApi();
  return useQuery<Broadcast, Error>({
    queryKey: keys.broadcast(wid, id),
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/broadcasts/{broadcast_id}", { params: { path: { wid, broadcast_id: id } } })),
    refetchInterval: (query) => (query.state.data?.status === "sending" ? 5_000 : false),
  });
}

/** A page of the audience, 25 at a time, optionally one status. */
export function useBroadcastRecipients(wid: string, id: string, status: RecipientStatus | null, page: number, live: boolean) {
  const api = useApi();
  return useQuery<BroadcastRecipientList, Error>({
    queryKey: keys.broadcastRecipients(wid, id, status, page),
    placeholderData: keepPreviousData,
    refetchInterval: live ? 5_000 : false,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/broadcasts/{broadcast_id}/recipients", {
          params: {
            path: { wid, broadcast_id: id },
            query: { status: status ?? undefined, limit: RECIPIENT_PAGE, offset: page * RECIPIENT_PAGE },
          },
        }),
      ),
  });
}

/** The composer's preview: who gets it, who is skipped, the cost, the quota, a sample message.
 * Asked for again whenever the draft changes. */
export function useBroadcastPreview(wid: string, draft: BroadcastDraft | null) {
  const api = useApi();
  return useQuery<BroadcastPreview, Error>({
    queryKey: keys.broadcastPreview(wid, draft),
    enabled: draft !== null,
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    retry: false,
    queryFn: () =>
      unwrap(api.POST("/v1/w/{wid}/broadcasts/preview", { params: { path: { wid } }, body: draft as BroadcastDraft })),
  });
}

function invalidateAll(queryClient: ReturnType<typeof useQueryClient>, wid: string) {
  void queryClient.invalidateQueries({ queryKey: ["w", wid, "broadcasts"] });
}

export function useCreateBroadcast(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Broadcast, Error, BroadcastCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/broadcasts", { params: { path: { wid } }, body })),
    onSuccess: () => invalidateAll(queryClient, wid),
  });
}

export function useUpdateBroadcast(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Broadcast, Error, { id: string; body: BroadcastUpdate }>({
    mutationFn: ({ id, body }) =>
      unwrap(api.PATCH("/v1/w/{wid}/broadcasts/{broadcast_id}", { params: { path: { wid, broadcast_id: id } }, body })),
    onSuccess: () => invalidateAll(queryClient, wid),
  });
}

/** Send now (no time) or schedule (an ISO time with its time zone). */
export function useStartBroadcast(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Broadcast, Error, { id: string; scheduledAt?: string }>({
    mutationFn: ({ id, scheduledAt }) =>
      unwrap(
        api.POST("/v1/w/{wid}/broadcasts/{broadcast_id}/start", {
          params: { path: { wid, broadcast_id: id } },
          body: { scheduled_at: scheduledAt ?? null },
        }),
      ),
    onSuccess: () => invalidateAll(queryClient, wid),
  });
}

export type BroadcastAction = "pause" | "resume" | "cancel";

export function useBroadcastAction(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Broadcast, Error, { id: string; action: BroadcastAction }>({
    mutationFn: ({ id, action }) => {
      const params = { params: { path: { wid, broadcast_id: id } } };
      if (action === "pause") return unwrap(api.POST("/v1/w/{wid}/broadcasts/{broadcast_id}/pause", params));
      if (action === "resume") return unwrap(api.POST("/v1/w/{wid}/broadcasts/{broadcast_id}/resume", params));
      return unwrap(api.POST("/v1/w/{wid}/broadcasts/{broadcast_id}/cancel", params));
    },
    onSuccess: () => invalidateAll(queryClient, wid),
  });
}

export function useDeleteBroadcast(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/broadcasts/{broadcast_id}", { params: { path: { wid, broadcast_id: id } } })),
    onSuccess: () => invalidateAll(queryClient, wid),
  });
}
