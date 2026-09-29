/**
 * Ask Social Hood fixtures (PA): runs, steps, threads and action cards shaped like the API's, and
 * a helper that sends agent.* events through the real-time handler.
 */
import { act } from "@testing-library/react";
import type { QueryClient } from "@tanstack/react-query";

import type {
  AgentRun,
  AgentRunDetail,
  AgentRunEvent,
  AgentStep,
  AgentStepProgress,
  AgentThread,
  AutomationDraftAction,
  CommentReplyAction,
  ScheduleMessageAction,
} from "@/lib/api/types";
import { applyRealtimeEvent } from "@/lib/realtime/events";

export function agentRun(overrides: Partial<AgentRun> = {}): AgentRun {
  return {
    id: "r1",
    thread_id: "r1",
    request: "How did my latest post do?",
    source: "ask",
    mode: "read_only",
    status: "succeeded",
    requested_by: { id: "u1", name: "Zakaur Rahman" },
    answer: null,
    answer_refs: [],
    action_cards: [],
    credits: 0,
    error: null,
    created_at: "2026-09-29T10:00:00Z",
    started_at: "2026-09-29T10:00:01Z",
    completed_at: null,
    ...overrides,
  };
}

let stepSeq = 0;

export function agentStep(overrides: Partial<AgentStep> = {}): AgentStep {
  stepSeq += 1;
  return {
    id: `st${stepSeq}`,
    ordinal: 0,
    kind: "tool",
    tool: "get_latest_post",
    label: "Looking up your latest post",
    tier: "read",
    status: "succeeded",
    args: { account: "maple.bakery" },
    summary: "Reel from 28 Sep, 26 hours old",
    result: { post_id: "po1", age_hours: 26 },
    decision: null,
    verification: null,
    attempts: 1,
    latency_ms: 420,
    error: null,
    started_at: "2026-09-29T10:00:02Z",
    completed_at: "2026-09-29T10:00:02Z",
    ...overrides,
  };
}

export function runDetail(overrides: Partial<AgentRunDetail> = {}): AgentRunDetail {
  return {
    ...agentRun(),
    steps: [],
    plan: null,
    model: "gemini-2.5-flash",
    prompt_version: "agent.v1",
    ...overrides,
  };
}

export function agentThread(overrides: Partial<AgentThread> = {}): AgentThread {
  return {
    id: "r1",
    title: "How did my latest post do?",
    run_count: 1,
    last_status: "succeeded",
    created_at: "2026-09-29T10:00:00Z",
    last_run_at: "2026-09-29T10:00:00Z",
    ...overrides,
  };
}

/** The answer of agent-architecture.html §14's first example, with a table and citations. */
export const LATEST_POST_ANSWER = [
  "Your latest reel is doing **better than usual** [1]. At 24 hours it reached 4,120 people, 42% above the median of your previous 10 reels [2].",
  "",
  "| Metric | This reel | Median of 10 |",
  "|---|---:|---:|",
  "| Reach | 4,120 | 2,900 |",
  "| Engagement rate | 6.1% | 4.4% |",
  "",
  "Time range: 26 Sep to 28 Sep · 10 earlier reels compared.",
].join("\n");

export const LATEST_POST_REFS: AgentRun["answer_refs"] = [
  { kind: "post", id: "po1", label: "Reel of 28 Sep" },
  { kind: "post", id: "po0", label: "Reel of 20 Sep" },
];

export function scheduleCard(overrides: Partial<ScheduleMessageAction> = {}): ScheduleMessageAction {
  return {
    kind: "schedule_message",
    label: "Schedule this message",
    route: "inbox/c1?schedule=1",
    note: "Priya's window closes 8:12 AM.",
    prefill: {
      conversation_id: "c1",
      text: "Hi Priya, your order ships Monday.",
      send_at: "2026-09-30T02:30:00Z",
      window_closes_at: "2026-09-30T02:42:00Z",
    },
    ...overrides,
  };
}

export function replyCard(overrides: Partial<CommentReplyAction> = {}): CommentReplyAction {
  return {
    kind: "reply_to_comment",
    label: "Reply to this comment",
    route: "comments/po1",
    note: null,
    prefill: { comment_id: "cm-kabir", post_id: "po1", text: "Sorry about the wait! It ships today.", private: false },
    ...overrides,
  };
}

export function draftCard(overrides: Partial<AutomationDraftAction> = {}): AutomationDraftAction {
  return {
    kind: "automation_draft",
    label: "Open the automation draft",
    route: "automations/new",
    note: null,
    prefill: {
      template_key: null,
      name: "Price DM",
      social_account_id: "a1",
      trigger: "dm_keyword",
      keywords: ["price", "cost"],
      action: "send_message",
      message_text: "Hi {first_name|there}! Our price list is here.",
      ai_instructions: null,
      public_reply_texts: [],
      post_scope: "all",
      media_item_ids: [],
    },
    ...overrides,
  };
}

// ---- events

function emit(queryClient: QueryClient, event: string, data: unknown) {
  act(() => applyRealtimeEvent(queryClient, "w1", { id: `${event}-${Math.random()}`, event, data: JSON.stringify(data) }));
}

export function emitStep(queryClient: QueryClient, runId: string, step: AgentStepProgress) {
  emit(queryClient, "agent.step", { run_id: runId, requested_by_user_id: "u1", step });
}

export function emitRun(queryClient: QueryClient, run: AgentRunEvent, completed = false) {
  emit(queryClient, completed ? "agent.completed" : "agent.run.updated", { run });
}
