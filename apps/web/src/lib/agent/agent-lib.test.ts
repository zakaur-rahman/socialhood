import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { keys } from "@/lib/api/queries/keys";
import type { AgentRunDetail, AnswerRef, Me } from "@/lib/api/types";
import { agentRun, agentStep, agentThread, draftCard, replyCard, runDetail, scheduleCard } from "@/test/agent";

import { addRunToThread, applyAgentRunEvent, applyAgentStepEvent, putRun, upsertStep, type RunPages, type ThreadPages } from "./cache";
import { definitionFromDraft, draftAccount } from "./draft";
import {
  durationText,
  followUpsFor,
  groupThreads,
  isActive,
  isFinal,
  modifierKey,
  runOutcome,
  secondsText,
  threadGroup,
  workedFor,
} from "./format";
import { actionPath, isAskPage, refPath } from "./routes";
import { toDefinition } from "@/lib/automations/definition";
import { account, automation } from "@/test/api";

describe("run statuses and outcomes (FR-AGT-06)", () => {
  it("knows which statuses are final", () => {
    expect(["queued", "planning", "running", "awaiting_approval"].every((s) => isActive(s as never))).toBe(true);
    expect(["succeeded", "partial", "failed", "cancelled", "expired"].every((s) => isFinal(s as never))).toBe(true);
  });

  it("names failed, out-of-credits, cancelled and expired runs explicitly", () => {
    expect(runOutcome("failed", { code: "ai_unavailable", message: "The AI didn't respond" })).toMatchObject({
      kind: "failed",
      body: "The AI didn't respond",
    });
    expect(runOutcome("failed", null)?.body).toBe("The AI didn't respond. Try again.");
    expect(runOutcome("partial", { code: "quota_exceeded", message: "You've used all 5,000 AI credits for this month." })).toMatchObject({
      kind: "quota",
      title: "Out of AI credits",
    });
    expect(runOutcome("cancelled", null)?.kind).toBe("cancelled");
    expect(runOutcome("expired", null)?.kind).toBe("expired");
    expect(runOutcome("succeeded", null)).toBeNull();
    expect(runOutcome("partial", null)).toBeNull();
  });

  it("says how long a run worked only when it has a start and an end", () => {
    expect(workedFor({ started_at: "2026-09-29T10:00:01Z", completed_at: "2026-09-29T10:00:07Z" })).toBe("6 s");
    expect(workedFor({ started_at: "2026-09-29T10:00:01Z", completed_at: "2026-09-29T10:01:06Z" })).toBe("1 min 5 s");
    expect(workedFor({ started_at: "2026-09-29T10:00:01Z", completed_at: "2026-09-29T10:00:01.2Z" })).toBe("1 s");
    expect(workedFor({ started_at: null, completed_at: "2026-09-29T10:00:07Z" })).toBeNull();
    expect(workedFor({ started_at: "2026-09-29T10:00:01Z", completed_at: null })).toBeNull();
    expect(secondsText(120_000)).toBe("2 min");
  });

  it("picks follow-ups from what an answer cited, in turn per kind, never the question just asked", () => {
    const post = { kind: "post" as const };
    const conversation = { kind: "conversation" as const };
    expect(followUpsFor([post, post], "How did my latest post do?")).toEqual([
      "Show the negative comments on this post",
      "Compare it with my previous post",
    ]);
    expect(followUpsFor([post, conversation], "x")).toEqual([
      "Show the negative comments on this post",
      "Which conversations need a reply today?",
      "Compare it with my previous post",
    ]);
    expect(followUpsFor([conversation], "Which conversations need a reply today?")).toEqual(["Summarise this conversation"]);
    expect(followUpsFor([], "x")).toEqual(["Which posts beat my average this month?", "What are people complaining about this week?"]);
  });

  it("groups threads by calendar day in the workspace time zone", () => {
    const now = new Date("2026-09-30T20:00:00Z"); // 1 Oct 01:30 in Kolkata
    const zone = "Asia/Kolkata";
    expect(threadGroup("2026-09-30T19:00:00Z", zone, now)).toBe("Today"); // 1 Oct 00:30
    expect(threadGroup("2026-09-30T18:00:00Z", zone, now)).toBe("Yesterday"); // 30 Sep 23:30
    expect(threadGroup("2026-09-25T10:00:00Z", zone, now)).toBe("Previous 7 days");
    expect(threadGroup("2026-09-20T10:00:00Z", zone, now)).toBe("Older");
    // The same instants in UTC fall on other days.
    expect(threadGroup("2026-09-30T18:00:00Z", "UTC", now)).toBe("Today");
    const grouped = groupThreads(
      [
        { id: "a", last_run_at: "2026-09-30T19:00:00Z" },
        { id: "b", last_run_at: "2026-09-20T10:00:00Z" },
        { id: "c", last_run_at: "2026-09-30T19:30:00Z" },
      ],
      zone,
      now,
    );
    expect(grouped.map((g) => [g.group, g.items.map((i) => i.id)])).toEqual([
      ["Today", ["a", "c"]],
      ["Older", ["b"]],
    ]);
  });

  it("formats durations and the shortcut's modifier", () => {
    expect(durationText(420)).toBe("420 ms");
    expect(durationText(4200)).toBe("4.2 s");
    expect(durationText(65_000)).toBe("1 min 5 s");
    expect(durationText(null)).toBe("—");
    expect(modifierKey("MacIntel")).toBe("⌘");
    expect(modifierKey("Win32")).toBe("Ctrl");
  });
});

describe("where citations and action cards lead (FR-AGT-01, FR-AGT-03)", () => {
  const ref = (kind: AnswerRef["kind"]): AnswerRef => ({ kind, id: "x1", label: "x" });

  it("opens each cited record's screen, relative to the workspace", () => {
    expect(refPath(ref("post"))).toBe("comments/x1");
    expect(refPath(ref("conversation"))).toBe("inbox/x1");
    expect(refPath(ref("automation"))).toBe("automations/x1");
    expect(refPath(ref("scheduled_post"))).toBe("schedule/x1");
    expect(refPath(ref("knowledge_source"))).toBe("knowledge");
    // A comment opens its post and a scheduled message its conversation (the parent)…
    expect(refPath({ ...ref("comment"), parent_id: "p1" })).toBe("comments/p1");
    expect(refPath({ ...ref("scheduled_message"), parent_id: "c1" })).toBe("inbox/c1");
    // …or, with no parent in the reference, the nearest list.
    expect(refPath(ref("comment"))).toBe("comments");
    expect(refPath(ref("scheduled_message"))).toBe("inbox");
  });

  it("uses a card's route when it is a plain workspace path, else the prefill's screen", () => {
    expect(actionPath(scheduleCard())).toBe("inbox/c1?schedule=1");
    expect(actionPath(scheduleCard({ route: "/inbox/c1?schedule=1" }))).toBe("inbox/c1?schedule=1");
    expect(actionPath(scheduleCard({ route: "https://evil.example/x" }))).toBe("inbox/c1?schedule=1");
    expect(actionPath(replyCard({ route: "//evil.example" }))).toBe("comments/po1");
    expect(actionPath(replyCard({ route: "../../x" }))).toBe("comments/po1");
    expect(actionPath(draftCard({ route: "javascript:alert(1)" }))).toBe("automations/new");
    expect(actionPath(draftCard())).toBe("automations/new");
  });

  it("knows the Ask page", () => {
    expect(isAskPage("/w/maple/ask")).toBe(true);
    expect(isAskPage("/w/maple/inbox")).toBe(false);
    expect(isAskPage("/w/maple/ask/x")).toBe(false);
  });
});

describe("agent cache patching (TR-FE-04)", () => {
  function client() {
    return new QueryClient({ defaultOptions: { queries: { retry: false } } });
  }

  it("upserts steps by id in ordinal order, keeping a summary the event doesn't repeat", () => {
    const first = agentStep({ id: "a", ordinal: 0, status: "running", summary: null });
    let steps = upsertStep([], first);
    steps = upsertStep(steps, {
      id: "b",
      ordinal: 1,
      kind: "tool",
      tool: "compare_posts",
      label: "Comparing with 10 earlier posts",
      status: "running",
      summary: null,
      latency_ms: 0,
    });
    steps = upsertStep(steps, { id: "a", ordinal: 0, kind: "tool", tool: "get_latest_post", label: first.label, status: "succeeded", summary: "Found it", latency_ms: 300 });
    expect(steps.map((s) => [s.id, s.status])).toEqual([
      ["a", "succeeded"],
      ["b", "running"],
    ]);
    const again = upsertStep(steps, { id: "a", ordinal: 0, kind: "tool", tool: null, label: first.label, status: "succeeded", summary: null, latency_ms: 300 });
    expect(again[0].summary).toBe("Found it");
    // A step first seen through an event gets empty trace fields until the run is fetched.
    expect(steps[1]).toMatchObject({ args: {}, attempts: 0, result: null });
  });

  it("patches a watched run's steps and status; completion refetches the run, its thread and history", async () => {
    const queryClient = client();
    queryClient.setQueryData(keys.me, { id: "u1" } as Me);
    const run = agentRun({ id: "r1", thread_id: "t1", status: "running" });
    putRun(queryClient, "w1", run);
    addRunToThread(queryClient, "w1", run);
    queryClient.setQueryData<ThreadPages>(keys.agentThreads("w1"), {
      pages: [{ items: [agentThread({ id: "t1", last_status: "running" })], next_cursor: null }],
      pageParams: [null],
    });

    applyAgentStepEvent(queryClient, "w1", {
      run_id: "r1",
      step: { id: "s1", ordinal: 0, kind: "tool", tool: "get_latest_post", label: "Looking up your latest post", status: "running", summary: null, latency_ms: 0 },
    });
    expect(queryClient.getQueryData<AgentRunDetail>(keys.agentRun("w1", "r1"))?.steps).toHaveLength(1);

    applyAgentRunEvent(queryClient, "w1", { id: "r1", thread_id: "t1", status: "succeeded", step_count: 2, requested_by_user_id: "u1" }, true);
    expect(queryClient.getQueryData<AgentRunDetail>(keys.agentRun("w1", "r1"))?.status).toBe("succeeded");
    expect(queryClient.getQueryData<RunPages>(keys.agentThreadRuns("w1", "t1"))?.pages[0].items[0].status).toBe("succeeded");
    expect(queryClient.getQueryData<ThreadPages>(keys.agentThreads("w1"))?.pages[0].items[0].last_status).toBe("succeeded");
    expect(queryClient.getQueryState(keys.agentRun("w1", "r1"))?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(keys.agentThreadRuns("w1", "t1"))?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(keys.agentThreads("w1"))?.isInvalidated).toBe(true);
  });

  it("ignores steps of runs nobody watches, and leaves thread titles alone for another member's run", () => {
    const queryClient = client();
    queryClient.setQueryData(keys.me, { id: "u1" } as Me);
    queryClient.setQueryData<ThreadPages>(keys.agentThreads("w1"), { pages: [{ items: [], next_cursor: null }], pageParams: [null] });
    applyAgentStepEvent(queryClient, "w1", {
      run_id: "r9",
      step: { id: "s1", ordinal: 0, kind: "tool", tool: null, label: "x", status: "running", summary: null, latency_ms: 0 },
    });
    expect(queryClient.getQueryData(keys.agentRun("w1", "r9"))).toBeUndefined();
    applyAgentRunEvent(queryClient, "w1", { id: "r9", thread_id: "t9", status: "succeeded", step_count: 1, requested_by_user_id: "u2" }, true);
    expect(queryClient.getQueryState(keys.agentThreads("w1"))?.isInvalidated).toBe(false);
  });

  it("a cancel keeps the steps already shown", () => {
    const queryClient = client();
    queryClient.setQueryData(keys.agentRun("w1", "r1"), runDetail({ status: "running", steps: [agentStep()] }));
    putRun(queryClient, "w1", agentRun({ status: "cancelled" }));
    const detail = queryClient.getQueryData<AgentRunDetail>(keys.agentRun("w1", "r1"));
    expect(detail?.status).toBe("cancelled");
    expect(detail?.steps).toHaveLength(1);
  });
});

describe("automation drafts from Ask Social Hood (FR-AGT-03)", () => {
  it("lays the prepared values over a new draft in the editor's terms", () => {
    const base = toDefinition(automation({ trigger: null, keywords: [], action: null, message_text: null, public_reply_texts: [] }));
    const body = definitionFromDraft(base, draftCard().prefill);
    expect(body).toMatchObject({
      name: "Price DM",
      trigger: "dm_keyword",
      keywords: ["price", "cost"],
      action: "send_message",
      message_text: "Hi {first_name|there}! Our price list is here.",
      post_scope: "all",
    });
  });

  it("starts comment triggers the editor's way (tap first on; Any comment on chosen posts)", () => {
    const base = toDefinition(
      automation({ trigger: null, keywords: [], opening_text: null, opening_button: null, public_reply_texts: [] }),
    );
    const body = definitionFromDraft(base, {
      ...draftCard().prefill,
      trigger: "comment_any",
      keywords: [],
      public_reply_texts: ["Sent you a DM!"],
    });
    expect(body).toMatchObject({ trigger: "comment_any", confirm_first: true, post_scope: "selected" });
    expect(body.public_reply_texts).toEqual(["Sent you a DM!"]);
  });

  it("picks the draft's account, else the only one", () => {
    const one = account({ id: "a1" });
    const two = account({ id: "a2", username: "maple.two" });
    expect(draftAccount(draftCard().prefill, [one, two])).toBe("a1");
    expect(draftAccount({ ...draftCard().prefill, social_account_id: null }, [two])).toBe("a2");
    expect(draftAccount({ ...draftCard().prefill, social_account_id: "gone" }, [one, two])).toBeNull();
  });
});
