"use client";

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type {
  KnowledgeGap,
  KnowledgeGapList,
  KnowledgeSource,
  KnowledgeSourceCreate,
  KnowledgeSourceList,
  KnowledgeSourcePatch,
  KnowledgeTestResult,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** How often the list is refreshed while a source is still being read (FR-KB-02). */
export const PROCESSING_POLL_MS = 3_000;

export function isProcessing(source: Pick<KnowledgeSource, "status">): boolean {
  return source.status === "pending" || source.status === "processing";
}

function patchSources(queryClient: QueryClient, wid: string, change: (items: KnowledgeSource[]) => KnowledgeSource[]) {
  queryClient.setQueryData<KnowledgeSourceList>(keys.knowledgeSources(wid), (data) =>
    data ? { ...data, items: change(data.items) } : data,
  );
}

function removeGap(queryClient: QueryClient, wid: string, gapId: string) {
  queryClient.setQueryData<KnowledgeGapList>(keys.knowledgeGaps(wid), (data) =>
    data ? { ...data, items: data.items.filter((gap) => gap.id !== gapId) } : data,
  );
}

// ---- sources (FR-KB-01, FR-KB-02)

/** Sources with the plan usage; polled while any source is processing (no event for ingestion). */
export function useKnowledgeSources(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<KnowledgeSourceList>({
    queryKey: keys.knowledgeSources(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/knowledge-sources", { params: { path: { wid } } })),
    refetchInterval: (query) => (query.state.data?.items.some(isProcessing) ? PROCESSING_POLL_MS : false),
  });
}

/** 402 quota_exceeded over the plan's knowledge characters; a gap_id answers that gap (F-17). */
export function useCreateKnowledgeSource(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<KnowledgeSource, Error, KnowledgeSourceCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/knowledge-sources", { params: { path: { wid } }, body })),
    onSuccess: async (source, body) => {
      patchSources(queryClient, wid, (items) => [source, ...items.filter((item) => item.id !== source.id)]);
      if (body.gap_id) removeGap(queryClient, wid, body.gap_id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.knowledgeSources(wid) }),
        body.gap_id ? queryClient.invalidateQueries({ queryKey: keys.knowledgeGaps(wid) }) : null,
        queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] }),
      ]);
    },
  });
}

/** Edits re-ingest the source; `reingest` fetches a web page or reads a file again. */
export function useUpdateKnowledgeSource(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<KnowledgeSource, Error, { id: string; patch: Partial<KnowledgeSourcePatch> }>({
    mutationFn: ({ id, patch }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/knowledge-sources/{source_id}", {
          params: { path: { wid, source_id: id } },
          body: { reingest: false, ...patch },
        }),
      ),
    onSuccess: (source) => {
      patchSources(queryClient, wid, (items) => items.map((item) => (item.id === source.id ? source : item)));
      void queryClient.invalidateQueries({ queryKey: keys.knowledgeSources(wid) });
    },
  });
}

export function useDeleteKnowledgeSource(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/knowledge-sources/{source_id}", { params: { path: { wid, source_id: id } } })),
    onSuccess: async (_, id) => {
      patchSources(queryClient, wid, (items) => items.filter((item) => item.id !== id));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.knowledgeSources(wid) }),
        queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] }),
      ]);
    },
  });
}

// ---- the test box (FR-KB-03): nothing is stored or sent

export function useTestKnowledge(wid: string) {
  const api = useApi();
  return useMutation<KnowledgeTestResult, Error, string>({
    mutationFn: (question) =>
      unwrap(api.POST("/v1/w/{wid}/knowledge/test", { params: { path: { wid } }, body: { question } })),
  });
}

// ---- questions the AI couldn't answer (FR-KB-06, F-17)

/** Open gaps from the last 30 days, most asked first. */
export function useKnowledgeGaps(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<KnowledgeGapList>({
    queryKey: keys.knowledgeGaps(wid),
    enabled,
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/knowledge-gaps", { params: { path: { wid }, query: { status: "open" } } })),
  });
}

/** Dismiss hides the topic until a customer asks again; the row leaves at once. */
export function useDismissKnowledgeGap(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<KnowledgeGap, Error, string, { previous?: KnowledgeGapList }>({
    mutationFn: (id) =>
      unwrap(api.POST("/v1/w/{wid}/knowledge-gaps/{gap_id}/dismiss", { params: { path: { wid, gap_id: id } } })),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: keys.knowledgeGaps(wid) });
      const previous = queryClient.getQueryData<KnowledgeGapList>(keys.knowledgeGaps(wid));
      removeGap(queryClient, wid, id);
      return { previous };
    },
    onError: (_error, _id, context) => {
      if (context?.previous) queryClient.setQueryData(keys.knowledgeGaps(wid), context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] }),
  });
}
