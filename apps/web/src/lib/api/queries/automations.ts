"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";

import { useApi } from "../provider";
import type {
  Automation,
  AutomationCreate,
  AutomationDefinition,
  AutomationList,
  AutomationRunList,
  AutomationsSummary,
  AutomationStats,
  AutomationTemplate,
  AutomationTest,
  AutomationTestResult,
  PostList,
  RunResult,
} from "../types";
import { keys, type AutomationFilters } from "./keys";
import { expectOk, unwrap } from "./unwrap";

export type RunPages = InfiniteData<AutomationRunList, string | null>;
export type PostPages = InfiniteData<PostList, string | null>;

/** Every cached list (all filter combinations) of the workspace's automations. */
function listsKey(wid: string) {
  return [...keys.automationLists(wid), "list"] as const;
}

/** Apply a change to every cached list, so the row updates wherever it shows. */
function patchLists(queryClient: QueryClient, wid: string, change: (items: Automation[]) => Automation[]) {
  queryClient.setQueriesData<AutomationList>({ queryKey: listsKey(wid) }, (data) =>
    data ? { ...data, items: change(data.items) } : data,
  );
}

function replaceEverywhere(queryClient: QueryClient, wid: string, automation: Automation) {
  queryClient.setQueryData(keys.automation(wid, automation.id), automation);
  patchLists(queryClient, wid, (items) => items.map((item) => (item.id === automation.id ? automation : item)));
}

function refreshLists(queryClient: QueryClient, wid: string) {
  return queryClient.invalidateQueries({ queryKey: keys.automationLists(wid) });
}

// ---- reading

/** FR-AUT-12: the template gallery. Templates are defined in code, so they never go stale. */
export function useAutomationTemplates(wid: string) {
  const api = useApi();
  return useQuery<AutomationTemplate[]>({
    queryKey: keys.automationTemplates(wid),
    staleTime: Infinity,
    queryFn: async () =>
      (await unwrap(api.GET("/v1/w/{wid}/automation-templates", { params: { path: { wid } } }))).items,
  });
}

/** UX-SCR-02: the whole list (the endpoint has no pages), filtered and sorted server-side. */
export function useAutomations(wid: string, filters: AutomationFilters) {
  const api = useApi();
  return useQuery<AutomationList>({
    queryKey: keys.automations(wid, filters),
    // A new search or filter keeps the rows on screen until its results arrive.
    placeholderData: (previous) => previous,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/automations", {
          params: {
            path: { wid },
            query: {
              account_id: filters.accountId ?? undefined,
              status: filters.status ?? undefined,
              trigger: filters.trigger ?? undefined,
              q: filters.q.trim() || undefined,
              sort: filters.sort,
            },
          },
        }),
      ),
  });
}

/** The figures strip; while DMs wait in a queue the ETA is refreshed every minute. */
export function useAutomationsSummary(wid: string) {
  const api = useApi();
  return useQuery<AutomationsSummary>({
    queryKey: keys.automationsSummary(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/automations/summary", { params: { path: { wid } } })),
    refetchInterval: (query) => (query.state.data?.waiting ? 60_000 : false),
  });
}

/** One automation; while DMs wait in its queue the count and ETA refresh every minute. */
export function useAutomation(wid: string, id: string) {
  const api = useApi();
  return useQuery<Automation>({
    queryKey: keys.automation(wid, id),
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/automations/{automation_id}", { params: { path: { wid, automation_id: id } } })),
    refetchInterval: (query) => (query.state.data?.queue.waiting ? 60_000 : false),
  });
}

/** UX-SCR-12 runs, newest first, filterable by result. */
export function useAutomationRuns(wid: string, id: string, result: RunResult | null, enabled = true) {
  const api = useApi();
  return useInfiniteQuery<AutomationRunList, Error, RunPages, ReturnType<typeof keys.automationRuns>, string | null>({
    queryKey: keys.automationRuns(wid, id, result),
    enabled,
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/automations/{automation_id}/runs", {
          params: {
            path: { wid, automation_id: id },
            query: { result: result ?? undefined, cursor: pageParam ?? undefined, limit: 50 },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** FR-AUT-16 results for 7 or 30 days. */
export function useAutomationStats(wid: string, id: string, days: 7 | 30, enabled = true) {
  const api = useApi();
  return useQuery<AutomationStats>({
    queryKey: keys.automationStats(wid, id, days),
    enabled,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/automations/{automation_id}/stats", {
          params: { path: { wid, automation_id: id }, query: { days } },
        }),
      ),
  });
}

/** The post picker (UX-SCR-03): the account's synced posts, newest first, searchable by caption. */
export function usePosts(wid: string, accountId: string | null, q: string, enabled = true) {
  const api = useApi();
  return useInfiniteQuery<PostList, Error, PostPages, ReturnType<typeof keys.posts>, string | null>({
    queryKey: keys.posts(wid, accountId, q.trim()),
    enabled: enabled && Boolean(accountId),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/posts", {
          params: {
            path: { wid },
            query: {
              account_id: accountId ?? undefined,
              q: q.trim() || undefined,
              cursor: pageParam ?? undefined,
              limit: 24,
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

// ---- changing

/** F-11: a draft, blank or from a template. The editor opens on it without another fetch. */
export function useCreateAutomation(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Automation, Error, AutomationCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/automations", { params: { path: { wid } }, body })),
    onSuccess: (automation) => {
      queryClient.setQueryData(keys.automation(wid, automation.id), automation);
      void refreshLists(queryClient, wid);
    },
  });
}

/** The autosave PUT: the whole definition. The response carries overlaps and what is missing. */
export function useSaveAutomation(wid: string, id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Automation, Error, AutomationDefinition>({
    mutationFn: (body) =>
      unwrap(
        api.PUT("/v1/w/{wid}/automations/{automation_id}", {
          params: { path: { wid, automation_id: id } },
          body,
        }),
      ),
    onSuccess: (automation) => {
      queryClient.setQueryData(keys.automation(wid, automation.id), automation);
      void refreshLists(queryClient, wid);
    },
  });
}

function useStatusChange(wid: string, action: "activate" | "pause") {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Automation, Error, string>({
    mutationFn: (id) =>
      unwrap(
        action === "activate"
          ? api.POST("/v1/w/{wid}/automations/{automation_id}/activate", {
              params: { path: { wid, automation_id: id } },
            })
          : api.POST("/v1/w/{wid}/automations/{automation_id}/pause", {
              params: { path: { wid, automation_id: id } },
            }),
      ),
    onSuccess: (automation) => {
      replaceEverywhere(queryClient, wid, automation);
      void queryClient.invalidateQueries({ queryKey: keys.automationsSummary(wid) });
    },
  });
}

/** FR-AUT-02: 422 validation_error lists every missing or invalid field. */
export function useActivateAutomation(wid: string) {
  return useStatusChange(wid, "activate");
}

export function usePauseAutomation(wid: string) {
  return useStatusChange(wid, "pause");
}

export function useDuplicateAutomation(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Automation, Error, string>({
    mutationFn: (id) =>
      unwrap(
        api.POST("/v1/w/{wid}/automations/{automation_id}/duplicate", {
          params: { path: { wid, automation_id: id } },
        }),
      ),
    onSuccess: (automation) => {
      queryClient.setQueryData(keys.automation(wid, automation.id), automation);
      void refreshLists(queryClient, wid);
    },
  });
}

export function useDeleteAutomation(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/automations/{automation_id}", { params: { path: { wid, automation_id: id } } }),
      ),
    onSuccess: (_, id) => {
      patchLists(queryClient, wid, (items) => items.filter((item) => item.id !== id));
      queryClient.removeQueries({ queryKey: keys.automation(wid, id) });
      void queryClient.invalidateQueries({ queryKey: keys.automationsSummary(wid) });
    },
  });
}

/** FR-AUT-19: pause several at once; the rows switch off straight away. */
export function useBulkPause(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string[]>({
    mutationFn: (ids) =>
      expectOk(api.POST("/v1/w/{wid}/automations/pause", { params: { path: { wid } }, body: { ids } })),
    onSuccess: (_, ids) => {
      patchLists(queryClient, wid, (items) =>
        items.map((item) =>
          ids.includes(item.id) && item.status === "active"
            ? { ...item, status: "paused", display_status: "paused" }
            : item,
        ),
      );
      void refreshLists(queryClient, wid);
    },
  });
}

/**
 * FR-AUT-15: the account's automations in their new order. The rows move at once; a failure
 * puts them back by refetching.
 */
export function useUpdatePriorities(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, { accountId: string; orderedIds: string[] }>({
    mutationFn: ({ accountId, orderedIds }) =>
      expectOk(
        api.PUT("/v1/w/{wid}/automations/priorities", {
          params: { path: { wid } },
          body: { social_account_id: accountId, ordered_ids: orderedIds },
        }),
      ),
    onMutate: ({ orderedIds }) => {
      const rank = new Map(orderedIds.map((id, index) => [id, index + 1]));
      patchLists(queryClient, wid, (items) =>
        items.map((item) => (rank.has(item.id) ? { ...item, priority: rank.get(item.id) ?? item.priority } : item)),
      );
    },
    onError: () => void refreshLists(queryClient, wid),
  });
}

/** What would happen for a message or comment; nothing is sent. */
export function useTestAutomation(wid: string, id: string) {
  const api = useApi();
  return useMutation<AutomationTestResult, Error, AutomationTest>({
    mutationFn: (body) =>
      unwrap(
        api.POST("/v1/w/{wid}/automations/{automation_id}/test", {
          params: { path: { wid, automation_id: id } },
          body,
        }),
      ),
  });
}
