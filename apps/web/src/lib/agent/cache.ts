/**
 * Cache patching for Ask Social Hood (TR-FE-04). Mutations and the agent.* events both go through
 * these functions. Events carry ids, statuses and plain-word steps only (never the request or the
 * answer), so on agent.completed the run is fetched again for its answer.
 */
import type { InfiniteData, QueryClient } from "@tanstack/react-query";

import { keys } from "@/lib/api/queries/keys";
import type {
  AgentRun,
  AgentRunDetail,
  AgentRunEvent,
  AgentRunList,
  AgentStep,
  AgentStepEvent,
  AgentStepProgress,
  AgentThreadList,
  Me,
} from "@/lib/api/types";

export type RunPages = InfiniteData<AgentRunList, string | null>;
export type ThreadPages = InfiniteData<AgentThreadList, string | null>;

function patchRunPages(
  queryClient: QueryClient,
  wid: string,
  id: string,
  patch: (run: AgentRun) => AgentRun,
): void {
  queryClient.setQueriesData<RunPages>({ queryKey: keys.agentRunLists(wid) }, (data) => {
    if (!data || !data.pages.some((page) => page.items.some((run) => run.id === id))) return data;
    return {
      ...data,
      pages: data.pages.map((page) => ({
        ...page,
        items: page.items.map((run) => (run.id === id ? patch(run) : run)),
      })),
    };
  });
}

/** A run as the API returned it (create, cancel): the detail keeps its steps; lists get the run. */
export function putRun(queryClient: QueryClient, wid: string, run: AgentRun): void {
  queryClient.setQueryData<AgentRunDetail>(keys.agentRun(wid, run.id), (detail) =>
    detail ? { ...detail, ...run, steps: detail.steps } : { ...run, steps: [] },
  );
  patchRunPages(queryClient, wid, run.id, (current) => ({ ...current, ...run }));
}

/** A new run joins its thread's list, newest first (the thread may be new: its id is the run's). */
export function addRunToThread(queryClient: QueryClient, wid: string, run: AgentRun): void {
  queryClient.setQueryData<RunPages>(keys.agentThreadRuns(wid, run.thread_id), (data) => {
    if (!data || data.pages.length === 0) {
      return { pages: [{ items: [run], next_cursor: null }], pageParams: [null] };
    }
    if (data.pages.some((page) => page.items.some((item) => item.id === run.id))) return data;
    const [first, ...rest] = data.pages;
    return { ...data, pages: [{ ...first, items: [run, ...first.items] }, ...rest] };
  });
}

/** A step the live list shows; fields the event doesn't carry wait for the run's next fetch. */
export function upsertStep(steps: AgentStep[], progress: AgentStepProgress): AgentStep[] {
  const index = steps.findIndex((step) => step.id === progress.id);
  let next: AgentStep[];
  if (index >= 0) {
    next = [...steps];
    next[index] = { ...steps[index], ...progress, summary: progress.summary ?? steps[index].summary ?? null };
  } else {
    next = [
      ...steps,
      {
        args: {},
        attempts: 0,
        result: null,
        tier: null,
        decision: null,
        verification: null,
        error: null,
        started_at: null,
        completed_at: null,
        ...progress,
      },
    ];
  }
  return next.sort((a, b) => a.ordinal - b.ordinal);
}

/** agent.step: a step started or finished. Only a run someone is watching has a detail to patch. */
export function applyAgentStepEvent(queryClient: QueryClient, wid: string, event: AgentStepEvent): void {
  queryClient.setQueryData<AgentRunDetail>(keys.agentRun(wid, event.run_id), (detail) =>
    detail ? { ...detail, steps: upsertStep(detail.steps, event.step) } : detail,
  );
}

/**
 * agent.run.updated (status or progress) and agent.completed (a final status). The status and
 * error patch every loaded copy; a completed run is fetched again for its answer, citations,
 * action cards and credits, with its thread's list and the thread titles.
 */
export function applyAgentRunEvent(
  queryClient: QueryClient,
  wid: string,
  event: AgentRunEvent,
  completed: boolean,
): void {
  const patch = { status: event.status, ...(event.error !== undefined ? { error: event.error } : {}) };
  queryClient.setQueryData<AgentRunDetail>(keys.agentRun(wid, event.id), (detail) =>
    detail ? { ...detail, ...patch } : detail,
  );
  patchRunPages(queryClient, wid, event.id, (run) => ({ ...run, ...patch }));
  queryClient.setQueryData<ThreadPages>(keys.agentThreads(wid), (data) =>
    data
      ? {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            items: page.items.map((thread) =>
              thread.id === event.thread_id ? { ...thread, last_status: event.status } : thread,
            ),
          })),
        }
      : data,
  );
  if (!completed) return;

  void queryClient.invalidateQueries({ queryKey: keys.agentRun(wid, event.id), exact: true });
  void queryClient.invalidateQueries({ queryKey: keys.agentThreadRuns(wid, event.thread_id), exact: true });
  void queryClient.invalidateQueries({ queryKey: keys.agentRunHistory(wid), exact: true });
  // Other members' runs share the stream; only the requester's thread titles change.
  const me = queryClient.getQueryData<Me>(keys.me)?.id;
  if (!me || !event.requested_by_user_id || event.requested_by_user_id === me) {
    void queryClient.invalidateQueries({ queryKey: keys.agentThreads(wid), exact: true });
  }
}

/** Runs of a thread, oldest first, as a conversation reads. */
export function threadRunsOldestFirst(data: RunPages | undefined): AgentRun[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.items).slice().reverse();
}
