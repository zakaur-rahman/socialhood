import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "@/lib/api/queries/keys";
import type { AgentRunDetail, AgentStepProgress } from "@/lib/api/types";
import { agentRun, runDetail } from "@/test/agent";
import { leadListVisual, leadRow, tableVisual, trendPoint, trendVisual } from "@/test/visuals";

import { controlGate, controlHints, costWords, currentSelection, offersControls } from "./controls";
import { REF_KIND_LABEL } from "./format";
import { applyAgentStepEvent, cancelVisualRefetches, VISUAL_REFETCH_MS, VISUAL_TOOLS } from "./cache";
import { moreLeads, prepareRepliesHint, prepareRepliesHints, scoreText, stageLabel } from "./leads";
import { refPath, visualPath } from "./routes";
import { cellText, moreRows } from "./tables";
import { gapsNote, plotTrend, pointLabel, pointRow, trendFacts } from "./trend";

describe("plotTrend (VIS-07): a gap breaks the line and is never drawn as zero", () => {
  it("lays known points out left to right, higher values higher up, from a zero baseline", () => {
    const { runs, last, gaps } = plotTrend([{ value: 0 }, { value: 50 }, { value: 100 }], 100, 50, 0);
    expect(gaps).toBe(0);
    expect(runs).toHaveLength(1);
    expect(runs[0].map(([x]) => x)).toEqual([0, 50, 100]);
    expect(runs[0].map(([, y]) => y)).toEqual([50, 25, 0]); // 0 sits on the baseline, the top value at the top
    expect(last).toEqual([100, 0]);
  });

  it("ends a run at a gap and starts another after it", () => {
    const { runs, gaps } = plotTrend(trendVisual().points, 300, 96);
    expect(gaps).toBe(1);
    expect(runs.map((run) => run.length)).toEqual([2, 2]);
  });

  it("a lone reading between two gaps is its own one-point run", () => {
    const { runs } = plotTrend([{ value: null }, { value: 5 }, { value: null }], 300, 96);
    expect(runs).toEqual([[[150, 4]]]);
  });

  it("nothing is drawn for a series with no reading", () => {
    const plotted = plotTrend([{ value: null }, { value: null }], 300, 96);
    expect(plotted.runs).toEqual([]);
    expect(plotted.last).toBeNull();
    expect(plotted.gaps).toBe(2);
  });

  it("a series of zeros stays on the baseline instead of dividing by zero", () => {
    const { runs } = plotTrend([{ value: 0 }, { value: 0 }], 100, 50);
    expect(runs[0].every(([, y]) => Number.isFinite(y) && y === 46)).toBe(true);
  });
});

describe("trend words (VIS-07)", () => {
  it("labels a day and a week", () => {
    expect(pointLabel({ day: "2026-10-12" }, "day")).toBe("12 Oct");
    expect(pointLabel({ day: "2026-10-12" }, "week")).toBe("Week of 12 Oct");
  });

  it("a table row has the figure, or 'No reading' for a gap", () => {
    const visual = trendVisual();
    expect(pointRow(trendPoint(1, 1200), visual)).toEqual({ label: "1 Oct", figure: "1,200" });
    expect(pointRow(trendPoint(3, null), visual)).toEqual({ label: "3 Oct", figure: "No reading" });
  });

  it("facts name the latest, lowest and highest with their days", () => {
    expect(trendFacts(trendVisual())).toEqual([
      { label: "Latest", value: "150", day: "5 Oct" },
      { label: "Lowest", value: "90", day: "4 Oct" },
      { label: "Highest", value: "150", day: "5 Oct" },
    ]);
    expect(trendFacts(trendVisual({ first: null, last: null, lowest: null, highest: null }))).toEqual([]);
  });

  it("says how many readings are missing, and nothing when none is", () => {
    expect(gapsNote(trendVisual())).toBe("4 of 5 days have a reading. The line breaks where there is none.");
    expect(gapsNote(trendVisual({ known_points: 5 }))).toBeNull();
    expect(gapsNote({ ...trendVisual(), granularity: "week" })).toContain("weeks");
  });
});

describe("lead list words (VIS-08, VIS-12)", () => {
  it("scores read 'No score' when there is none, never 0", () => {
    expect(scoreText(82)).toBe("Score 82");
    expect(scoreText(0)).toBe("Score 0"); // a real zero is a score
    expect(scoreText(null)).toBe("No score");
    expect(scoreText(undefined)).toBe("No score");
  });

  it("stages and the count of leads the list doesn't show", () => {
    expect(stageLabel("follow_up")).toBe("Follow up");
    expect(moreLeads(leadListVisual())).toBe(2);
    expect(moreLeads(leadListVisual({ total: 1, items: [leadRow()] }))).toBe(0);
  });

  it("the follow-up is a structured hint with ids only; the API words the question", () => {
    const hints = prepareRepliesHints(["cv1", "cv2"]);
    expect(hints).toEqual({ reply_conversation_ids: ["cv1", "cv2"] });
    expect(JSON.stringify(hints)).not.toContain("Priya");
    expect(prepareRepliesHint(1)).toBe("Drafts a reply for the top lead. Nothing is sent.");
    expect(prepareRepliesHint(3)).toBe("Drafts a reply for the top 3 leads. Nothing is sent.");
  });
});

describe("table cells (VIS-09)", () => {
  const text = { format: "text" } as const;
  it("formats figures by column, keeps text, and shows a missing cell as a dash", () => {
    expect(cellText("INR 1598.00", text)).toBe("INR 1598.00");
    expect(cellText(1234, { format: "count" })).toBe("1,234");
    expect(cellText(6.14, { format: "percent" })).toBe("6.1%");
    expect(cellText(null, text)).toBe("—");
    expect(cellText("", text)).toBe("—");
    expect(cellText(0, { format: "count" })).toBe("0");
  });

  it("counts the rows the table doesn't show", () => {
    expect(moreRows(tableVisual())).toBe(12);
    expect(moreRows(tableVisual({ total: 2 }))).toBe(0);
  });
});

describe("links (VIS-08, VIS-09)", () => {
  it("a contact ref opens the Contacts page; a conversation ref opens the thread", () => {
    expect(refPath({ kind: "contact", id: "c1", label: "Priya" })).toBe("contacts");
    expect(refPath({ kind: "conversation", id: "cv1", label: "Priya" })).toBe("inbox/cv1");
  });

  it("a visual's 'more' link must be a plain workspace path", () => {
    expect(visualPath("inbox?view=needs_reply")).toBe("inbox?view=needs_reply");
    expect(visualPath("/orders")).toBe("orders");
    expect(visualPath(null)).toBeNull();
    expect(visualPath("")).toBeNull();
    for (const bad of ["https://evil.example/x", "//evil.example", "../etc", "inbox#frag", "javascript:alert(1)"]) {
      expect(visualPath(bad)).toBeNull();
    }
  });
});

describe("progressive visuals (VIS-10): a finished visual-producing step refetches the run, debounced", () => {
  let queryClient: QueryClient;
  const step = (overrides: Partial<AgentStepProgress> = {}): AgentStepProgress => ({
    id: "s1",
    ordinal: 0,
    kind: "tool",
    tool: "compare_periods",
    label: "Comparing two periods",
    status: "succeeded",
    summary: null,
    latency_ms: 40,
    ...overrides,
  });
  const invalidated = () => queryClient.getQueryState(keys.agentRun("w1", "r1"))?.isInvalidated ?? false;

  beforeEach(() => {
    vi.useFakeTimers();
    queryClient = new QueryClient();
    queryClient.setQueryData<AgentRunDetail>(keys.agentRun("w1", "r1"), runDetail({ ...agentRun({ id: "r1", status: "running" }), steps: [] }));
  });

  afterEach(() => {
    cancelVisualRefetches();
    vi.useRealTimers();
  });

  it("refetches the run once its step has finished, not before", () => {
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ status: "running" }) });
    vi.advanceTimersByTime(VISUAL_REFETCH_MS * 2);
    expect(invalidated()).toBe(false); // started: nothing to show yet

    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step() });
    expect(invalidated()).toBe(false); // waits for the debounce
    vi.advanceTimersByTime(VISUAL_REFETCH_MS);
    expect(invalidated()).toBe(true);
  });

  it("steps that finish together share one fetch", () => {
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ id: "s1" }) });
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ id: "s2", ordinal: 1, tool: "top_posts" }) });
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ id: "s3", ordinal: 2, tool: "list_contacts" }) });
    vi.advanceTimersByTime(VISUAL_REFETCH_MS);
    expect(spy).toHaveBeenCalledTimes(1);
    // A later step starts a new wait.
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ id: "s4", ordinal: 3, tool: "metric_trend" }) });
    vi.advanceTimersByTime(VISUAL_REFETCH_MS);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("a tool that makes no visual, or a failed step, costs no extra fetch", () => {
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ tool: "get_latest_post" }) });
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ status: "failed" }) });
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step({ tool: null, kind: "report" }) });
    vi.advanceTimersByTime(VISUAL_REFETCH_MS * 3);
    expect(spy).not.toHaveBeenCalled();
  });

  it("a run nobody is watching is not fetched", () => {
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    applyAgentStepEvent(queryClient, "w1", { run_id: "r9", step: step() });
    vi.advanceTimersByTime(VISUAL_REFETCH_MS * 3);
    expect(spy).not.toHaveBeenCalled();
    expect(queryClient.getQueryData(keys.agentRun("w1", "r9"))).toBeUndefined();
  });

  it("still patches the live step list, as before", () => {
    applyAgentStepEvent(queryClient, "w1", { run_id: "r1", step: step() });
    expect(queryClient.getQueryData<AgentRunDetail>(keys.agentRun("w1", "r1"))?.steps).toHaveLength(1);
  });

  it("lists the tools whose results can hold a visual", () => {
    expect([...VISUAL_TOOLS].sort()).toEqual(
      [
        "comment_topics",
        "compare_periods",
        "list_contacts",
        "list_orders",
        "metric_trend",
        "search_conversations",
        "sentiment_distribution",
        "top_posts",
      ].sort(),
    );
  });
});

describe("controls (VIS-11)", () => {
  const none = { rangeDays: null, platform: null } as const;

  it("reads the current choice from the visual's period and the run's follow-up", () => {
    expect(currentSelection(trendVisual({ period: { start: "a", end: "b", label: "x", days: 30 } }), null)).toEqual({
      rangeDays: 30,
      platform: null,
    });
    expect(currentSelection(trendVisual(), { range_days: 90, platform: "instagram" })).toEqual({
      rangeDays: 90,
      platform: "instagram",
    });
    // Five days is not one of the offered ranges: none is shown as chosen.
    expect(currentSelection(trendVisual(), null).rangeDays).toBeNull();
  });

  it("a change sends the whole selection, whitelisted values only", () => {
    expect(controlHints(none, { rangeDays: 7 })).toEqual({ range_days: 7 });
    expect(controlHints({ rangeDays: 7, platform: "all" }, { platform: "whatsapp" })).toEqual({
      range_days: 7,
      platform: "whatsapp",
    });
  });

  it("the gate explains, by plan and by credits left", () => {
    expect(controlGate(null)).toEqual({ ok: true });
    expect(controlGate({ limit: null, used: 9 })).toEqual({ ok: true });
    expect(controlGate({ limit: 200, used: 100 })).toEqual({ ok: true });
    expect(controlGate({ limit: 200, used: 196 })).toEqual({ ok: true });
    expect(controlGate({ limit: 0, used: 0 })).toMatchObject({ ok: false });
    expect(controlGate({ limit: 200, used: 200, resetsOn: "2026-11-01" })).toMatchObject({
      ok: false,
      reason: expect.stringContaining("used all 200 AI credits"),
    });
    expect(controlGate({ limit: 200, used: 197 })).toEqual({
      ok: false,
      reason: "You have 3 AI credits left this month, and a change can use up to 4.",
    });
    expect(costWords).toBe("About 2 to 4 AI credits");
  });

  it("offers controls on trends, comparisons and period rankings only", () => {
    expect(offersControls(trendVisual())).toBe(true);
    expect(offersControls(tableVisual())).toBe(false);
    expect(offersControls(leadListVisual())).toBe(false);
  });
});

describe("report refs (VIS-13)", () => {
  it("open the weekly report of the week, for one account when the ref names it", () => {
    const base = { id: "r1", label: "Weekly report, 5-11 Oct 2026", kind: "report" as const };
    expect(refPath({ ...base, week: "2026-10-05" })).toBe("reports?week=2026-10-05");
    expect(refPath({ ...base, week: "2026-10-05", parent_id: "123e4567-e89b-12d3-a456-426614174000" })).toBe(
      "reports?week=2026-10-05&account=123e4567-e89b-12d3-a456-426614174000"
    );
    // A malformed ref never builds an address from its text.
    expect(refPath({ ...base, week: "x&evil=1", parent_id: "../x" })).toBe("reports");
    expect(REF_KIND_LABEL.report).toBe("Weekly report");
  });
});
