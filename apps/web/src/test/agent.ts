/**
 * Ask Social Hood fixtures (PA): runs, steps, threads and action cards shaped like the API's, and
 * a helper that sends agent.* events through the real-time handler.
 */
import { act } from "@testing-library/react";
import type { QueryClient } from "@tanstack/react-query";

import type {
  AgentApproval,
  AgentRun,
  AgentRunDetail,
  AgentRunEvent,
  AgentStep,
  AgentStepProgress,
  AgentThread,
  AutomationDraftAction,
  CommentReplyAction,
  FlowProposalAction,
  MetricComparisonVisual,
  MetricDelta,
  RankedPostsVisual,
  ScheduleMessageAction,
  SegmentProposalAction,
  SentimentSummaryVisual,
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
    visuals: [],
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
    approvals: [],
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

// ---- proposed writes (GR-36): a card in the answer and the approval behind it

export function flowProposalCard(overrides: Partial<FlowProposalAction> = {}): FlowProposalAction {
  return {
    kind: "flow_proposal",
    label: "Review and approve",
    route: "automations",
    note: "Nothing is saved until you approve it.",
    approval_id: "ap1",
    title: "New automation: Price list on PRICE",
    lines: [
      "Starts on a comment with a keyword: “PRICE”.",
      "It's saved as a draft. Nothing is switched on.",
      "1. send “Here's our price list: example.com/prices”",
    ],
    automation_id: null,
    step_count: 1,
    ...overrides,
  };
}

export function segmentProposalCard(overrides: Partial<SegmentProposalAction> = {}): SegmentProposalAction {
  return {
    kind: "segment_proposal",
    label: "Review and approve",
    route: "contacts",
    note: "Nothing is saved until you approve it.",
    approval_id: "ap2",
    title: "New segment: VIPs with email",
    lines: ["Has the tag vip", "Has an email", "Matches 12 people right now. It always follows whoever matches, not a fixed list."],
    match_count: 12,
    ...overrides,
  };
}

/** The approval behind a proposal card: waiting, and the caller may decide it. */
export function approval(overrides: Partial<AgentApproval> = {}): AgentApproval {
  return {
    id: "ap1",
    run_id: "r1",
    step_id: "st1",
    request: "When someone comments PRICE send them the price list",
    tool: "propose_flow",
    label: "Drafting an automation for your approval",
    tier: "draft",
    summary: "New automation: Price list on PRICE",
    payload: { tool: "propose_flow", args: {} },
    lines: flowProposalCard().lines,
    match_count: null,
    step_count: 1,
    status: "pending",
    expires_at: "2026-09-30T10:00:00Z",
    can_decide: true,
    requested_by: { id: "u1", name: "Zakaur Rahman" },
    decided_by: null,
    decided_at: null,
    outcome: null,
    events: [],
    created_at: "2026-09-29T10:00:00Z",
    ...overrides,
  };
}

// ---- visuals (GR-38): shaped like the API's, with figures a person can check by eye

export function metricDelta(overrides: Partial<MetricDelta> = {}): MetricDelta {
  return {
    key: "reach",
    label: "Reach",
    format: "count",
    current: 11800,
    previous: 10000,
    change_pct: 18,
    direction: "up",
    tone: "good",
    current_coverage: null,
    previous_coverage: null,
    unavailable: null,
    ...overrides,
  };
}

export function comparisonVisual(overrides: Partial<MetricComparisonVisual> = {}): MetricComparisonVisual {
  return {
    kind: "metric_comparison",
    version: 1,
    title: "@maple.bakery: 1-22 Oct 2026 against 1-22 Sep 2026",
    current: { start: "2026-10-01", end: "2026-10-22", label: "1-22 Oct 2026", days: 22 },
    previous: { start: "2026-09-01", end: "2026-09-22", label: "1-22 Sep 2026", days: 22 },
    comparable: true,
    note: "Compared over the same 22 days of each period.",
    account_label: "@maple.bakery",
    metrics: [
      metricDelta(),
      metricDelta({ key: "comments", label: "Comments received", current: 91, previous: 100, change_pct: -9, direction: "down", tone: "bad" }),
      metricDelta({ key: "unfollows", label: "Unfollows", current: 30, previous: 20, change_pct: 50, direction: "up", tone: "bad" }),
    ],
    ...overrides,
  };
}

export function rankedVisual(overrides: Partial<RankedPostsVisual> = {}): RankedPostsVisual {
  return {
    kind: "ranked_posts",
    version: 1,
    title: "Top posts by reach",
    metric_key: "reach",
    metric_label: "Reach",
    format: "count",
    period: { start: "2026-10-01", end: "2026-10-22", label: "1-22 Oct 2026", days: 22 },
    age_label: "Latest figures",
    considered: 7,
    items: [
      { post_id: "po1", label: "Reel of 12 Oct", format: "reel", caption: "Summer sale", thumbnail_url: "https://cdn.example/a.jpg", value: 4120 },
      { post_id: "po2", label: "Post of 3 Oct", format: "feed", caption: null, thumbnail_url: null, value: 2900 },
    ],
    ...overrides,
  };
}

export function sentimentVisual(overrides: Partial<SentimentSummaryVisual> = {}): SentimentSummaryVisual {
  return {
    kind: "sentiment_summary",
    version: 1,
    title: "Comment sentiment",
    scope: "comments made 1-22 Oct 2026",
    period: { start: "2026-10-01", end: "2026-10-22", label: "1-22 Oct 2026", days: 22 },
    total: 120,
    positive: 60,
    neutral: 20,
    negative: 10,
    spam: 5,
    not_analysed: 25,
    topics: [
      { label: "price", count: 12 },
      { label: "colours", count: 1 },
    ],
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
