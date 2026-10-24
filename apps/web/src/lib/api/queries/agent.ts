"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";

import { addRunToThread, putRun, type RunPages, type ThreadPages } from "@/lib/agent/cache";
import { definitionFromDraft } from "@/lib/agent/draft";
import { isActive } from "@/lib/agent/format";
import { toDefinition } from "@/lib/automations/definition";

import { INLINE_PLAN_LIMITS, useApi } from "../provider";
import type {
  AgentApproval,
  AgentApprovalList,
  AgentPolicy,
  AgentRun,
  AgentRunCreate,
  AgentRunDetail,
  AgentRunList,
  AgentRunStatus,
  AgentThreadList,
  ApprovalStatus,
  Automation,
  AutomationDraftPrefill,
} from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

const THREAD_RUNS_PAGE = 20;
const THREADS_PAGE = 20;
/** Settings → Agent shows the history a page (of the API) at a time (C-066). */
const HISTORY_PAGE = 10;
/** The "Waiting for you" list and a run's cards: a handful at a time is plenty. */
const APPROVALS_PAGE = 50;

/**
 * agent.* events keep a working run fresh. This slower poll is the fallback for a stream that is
 * reconnecting, so a run never looks stuck.
 */
export const RUN_POLL_MS = 5_000;

// ---- reading

/** The caller's threads, most recent activity first (FR-AGT-01). */
export function useAgentThreads(wid: string, enabled = true) {
  const api = useApi();
  return useInfiniteQuery<AgentThreadList, Error, ThreadPages, ReturnType<typeof keys.agentThreads>, string | null>({
    queryKey: keys.agentThreads(wid),
    enabled,
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/agent/threads", {
          params: { path: { wid }, query: { cursor: pageParam ?? undefined, limit: THREADS_PAGE } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** One thread's runs, newest first; the conversation shows them reversed. */
export function useThreadRuns(wid: string, threadId: string | null) {
  const api = useApi();
  return useInfiniteQuery<AgentRunList, Error, RunPages, ReturnType<typeof keys.agentThreadRuns>, string | null>({
    queryKey: keys.agentThreadRuns(wid, threadId ?? ""),
    enabled: Boolean(threadId),
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/agent/runs", {
          params: {
            path: { wid },
            query: { thread_id: threadId ?? undefined, cursor: pageParam ?? undefined, limit: THREAD_RUNS_PAGE },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** A run with its steps (TR-AGT-08): live steps while it works, the full trace for history. */
export function useAgentRun(wid: string, runId: string | null, enabled = true) {
  const api = useApi();
  return useQuery<AgentRunDetail>({
    queryKey: keys.agentRun(wid, runId ?? ""),
    enabled: enabled && Boolean(runId),
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/agent/runs/{run_id}", { params: { path: { wid, run_id: runId ?? "" } } })),
    refetchInterval: (query) => (query.state.data && isActive(query.state.data.status) ? RUN_POLL_MS : false),
  });
}

/** Settings → Agent's narrowing of the history (C-066): statuses and request text. */
export type RunHistoryFilters = { statuses?: readonly AgentRunStatus[]; q?: string };

/**
 * FR-AGT-07: every run, newest first. Owners and admins get the workspace's; members their own.
 * With filters, only runs in those statuses whose request contains the text (C-066).
 */
export function useAgentRunHistory(wid: string, enabled = true, filters: RunHistoryFilters = {}) {
  const api = useApi();
  const statuses = filters.statuses ?? [];
  const q = filters.q?.trim() ?? "";
  const filtered = statuses.length > 0 || q !== "";
  return useInfiniteQuery<AgentRunList, Error, RunPages, QueryKey, string | null>({
    queryKey: filtered ? keys.agentRunHistoryFiltered(wid, statuses, q) : keys.agentRunHistory(wid),
    enabled,
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/agent/runs", {
          params: {
            path: { wid },
            query: {
              cursor: pageParam ?? undefined,
              limit: HISTORY_PAGE,
              ...(statuses.length > 0 ? { status: [...statuses] } : {}),
              ...(q ? { q } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** The agent's mode, switches and limits (admins). In R1 always read only with every switch off. */
export function useAgentPolicy(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<AgentPolicy>({
    queryKey: keys.agentPolicy(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/agent/policy", { params: { path: { wid } } })),
  });
}

/**
 * GR-36: the writes the agent proposed, soonest to expire first. Owners and admins get the
 * workspace's, members their own runs'. `status` defaults to the ones still waiting; a run's own
 * cards ask for every status of that run.
 */
export function useAgentApprovals(
  wid: string,
  filters: { status?: ApprovalStatus | "all"; runId?: string } = {},
  enabled = true,
) {
  const api = useApi();
  const status = filters.status ?? "pending";
  const runId = filters.runId ?? null;
  return useQuery<AgentApprovalList>({
    queryKey: keys.agentApprovals(wid, status, runId),
    enabled,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/agent/approvals", {
          params: { path: { wid }, query: { status, run_id: runId ?? undefined, limit: APPROVALS_PAGE } },
        }),
      ),
  });
}

// ---- changing

/**
 * FR-AGT-01: ask a question, in a thread or a new one (the new thread's id is the run's). 202 with
 * the queued run; 402 quota_exceeded when the AI credits are used up (nothing is stored).
 */
export function useAskAgent(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<AgentRun, Error, AgentRunCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/agent/runs", { params: { path: { wid } }, body })),
    onSuccess: (run) => {
      putRun(queryClient, wid, run);
      addRunToThread(queryClient, wid, run);
      // Steps may have started before this answer arrived; the next fetch has them.
      void queryClient.invalidateQueries({ queryKey: keys.agentRun(wid, run.id), exact: true });
      void queryClient.invalidateQueries({ queryKey: keys.agentThreads(wid), exact: true });
      void queryClient.invalidateQueries({ queryKey: keys.agentRunHistory(wid), exact: true });
    },
    // Out of credits, the question box says so beside the question, with Upgrade (AskConversation).
    meta: INLINE_PLAN_LIMITS,
  });
}

/**
 * FR-AGT-03 "Open the automation draft": after the member confirms, create a draft automation
 * (as the template gallery does) and fill it with the prepared values. It stays a draft; the
 * member edits and activates it in the editor. `applied` is false when only the create worked.
 */
export function useStartAutomationDraft(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<
    { automation: Automation; applied: boolean },
    Error,
    { draft: AutomationDraftPrefill; accountId: string | null }
  >({
    mutationFn: async ({ draft, accountId }) => {
      const created = await unwrap(
        api.POST("/v1/w/{wid}/automations", {
          params: { path: { wid } },
          body: { name: draft.name, social_account_id: accountId, template_key: draft.template_key ?? null },
        }),
      );
      try {
        const saved = await unwrap(
          api.PUT("/v1/w/{wid}/automations/{automation_id}", {
            params: { path: { wid, automation_id: created.id } },
            body: definitionFromDraft(toDefinition(created), draft),
          }),
        );
        return { automation: saved, applied: true };
      } catch {
        return { automation: created, applied: false };
      }
    },
    onSuccess: ({ automation }) => {
      queryClient.setQueryData(keys.automation(wid, automation.id), automation);
      void queryClient.invalidateQueries({ queryKey: keys.automationLists(wid) });
    },
  });
}

/** Stop at the next step (§9): the run becomes cancelled at once; finished steps are kept. */
export function useCancelAgentRun(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<AgentRun, Error, string>({
    mutationFn: (runId) =>
      unwrap(api.POST("/v1/w/{wid}/agent/runs/{run_id}/cancel", { params: { path: { wid, run_id: runId } } })),
    onSuccess: (run) => {
      putRun(queryClient, wid, run);
      void queryClient.invalidateQueries({ queryKey: keys.agentThreads(wid), exact: true });
    },
  });
}

/** After a decision: the lists, the run's trace, and what an approval may have saved. */
function refreshAfterDecision(queryClient: ReturnType<typeof useQueryClient>, wid: string, approval: AgentApproval) {
  void queryClient.invalidateQueries({ queryKey: keys.agentApprovalLists(wid) });
  void queryClient.invalidateQueries({ queryKey: keys.agentRun(wid, approval.run_id), exact: true });
  if (approval.outcome?.ok) {
    void queryClient.invalidateQueries({ queryKey: keys.automationLists(wid) });
    void queryClient.invalidateQueries({ queryKey: keys.contactSegments(wid) });
  }
}

/**
 * GR-36: approve a proposed write as shown, or with edited `args`. The API runs it through the
 * normal service. 200 with `outcome.ok` false means the service refused it (a name taken, a plan
 * limit): nothing was saved and the approval is still pending. 403 for a role that can't do it by
 * hand; 409 when it was decided or expired meanwhile.
 */
export function useApproveAgentApproval(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<AgentApproval, Error, { id: string; args?: Record<string, unknown> | null }>({
    mutationFn: ({ id, args }) =>
      unwrap(
        api.POST("/v1/w/{wid}/agent/approvals/{approval_id}/approve", {
          params: { path: { wid, approval_id: id } },
          body: { args: args ?? null },
        }),
      ),
    onSuccess: (approval) => refreshAfterDecision(queryClient, wid, approval),
    // A plan limit is shown on the card, beside the proposal.
    meta: INLINE_PLAN_LIMITS,
  });
}

/** GR-36: say no; nothing is saved. */
export function useRejectAgentApproval(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<AgentApproval, Error, string>({
    mutationFn: (id) =>
      unwrap(
        api.POST("/v1/w/{wid}/agent/approvals/{approval_id}/reject", {
          params: { path: { wid, approval_id: id } },
        }),
      ),
    onSuccess: (approval) => refreshAfterDecision(queryClient, wid, approval),
  });
}
