import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AgentRunDetail } from "@/lib/api/types";
import { json, problem, renderWithApi, workspace, type Call } from "@/test/api";
import { agentRun, agentStep, LATEST_POST_ANSWER, LATEST_POST_REFS, runDetail, scheduleCard } from "@/test/agent";

import { AgentSettingsPage } from "./AgentSettingsPage";

vi.mock("next/navigation", () => ({
  usePathname: () => "/w/maple/settings/agent",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const answered = runDetail({
  id: "r1",
  request: "How did my latest post do?",
  requested_by: { id: "u2", name: "Priya Nair" },
  answer: LATEST_POST_ANSWER,
  answer_refs: LATEST_POST_REFS,
  credits: 3,
  completed_at: "2026-09-29T10:00:09Z",
  action_cards: [scheduleCard()],
  steps: [
    agentStep({ id: "s1", ordinal: 0 }),
    agentStep({
      id: "s2",
      ordinal: 1,
      tool: "compare_posts",
      label: "Comparing with 10 earlier posts at 24 hours",
      args: { post_id: "po1", baseline: "previous", n: 10, at_age: "24h" },
      summary: "Reach 4,120 vs median 2,900 (+42%)",
      result: { reach: { value: 4120, median: 2900 } },
      latency_ms: 1300,
      attempts: 2,
    }),
    agentStep({
      id: "s3",
      ordinal: 2,
      tool: "sentiment_distribution",
      label: "Checking comment sentiment",
      status: "failed",
      summary: null,
      result: null,
      error: { code: "insights_missing", message: "Comments on this post aren't analysed yet" },
      verification: { verified: false, checked: ["comment analyses"], external_ids: [] },
    }),
  ],
});
const failed = runDetail({
  id: "r2",
  request: "Top posts this month",
  status: "failed",
  error: { code: "ai_unavailable", message: "The AI didn't respond" },
  created_at: "2026-09-29T09:00:00Z",
});

function handlers(
  runs: AgentRunDetail[] = [answered, failed],
  next: string | null = null,
  pick: (call: Call) => AgentRunDetail[] = () => runs,
) {
  return {
    "GET /v1/w/:wid/agent/policy": () =>
      json({
        mode: "read_only",
        permissions: {
          send_replies: false,
          schedule_messages: false,
          schedule_posts: false,
          create_automations: false,
          delete_automations: false,
          bulk_actions: false,
        },
        limits: { bulk_max: 50, writes_per_hour: 30, writes_per_day: 200 },
        updated_by: null,
        updated_at: "2026-09-29T00:00:00Z",
      }),
    "GET /v1/w/:wid/agent/runs": (call: Call) => {
      const cursor = call.url.searchParams.get("cursor");
      if (cursor === "page2") return json({ items: [agentRun({ id: "r3", request: "Oldest question" })], next_cursor: null });
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      return json({ items: pick(call).map(({ steps, plan, model, prompt_version, ...run }) => run), next_cursor: next });
    },
    "GET /v1/w/:wid/agent/runs/:id": (_: Call, p: Record<string, string>) => {
      const run = runs.find((item) => item.id === p.id);
      return run ? json(run) : problem(404, "not_found");
    },
  };
}

describe("Settings → Agent (FR-AGT-07, agent-architecture.html §12)", () => {
  it("shows the read-only mode with every write capability off and locked until later", async () => {
    renderWithApi(<AgentSettingsPage />, { handlers: handlers() });
    expect(await screen.findByText("Read only")).toBeInTheDocument();
    expect(screen.getByText(/doesn't send, schedule or change anything itself/)).toBeInTheDocument();
    const permissions = screen.getByRole("list", { name: "Agent permissions" });
    expect(within(permissions).getAllByText("Off")).toHaveLength(6);
    expect(within(permissions).getAllByText("Coming later")).toHaveLength(6);
    expect(within(permissions).getAllByRole("listitem").map((li) => li.querySelector("p")?.textContent)).toEqual([
      "Send replies",
      "Schedule messages",
      "Schedule posts",
      "Create automations",
      "Delete automations",
      "Bulk actions",
    ]);
  });

  it("lists every run with its request, who asked, outcome, credits and time", async () => {
    renderWithApi(<AgentSettingsPage />, { handlers: handlers() });
    const list = await screen.findByRole("list", { name: "Runs" });
    const rows = within(list).getAllByRole("button");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("How did my latest post do?");
    expect(rows[0]).toHaveTextContent("Priya Nair");
    expect(rows[0]).toHaveTextContent("Answered");
    expect(rows[0]).toHaveTextContent("3 credits");
    expect(rows[1]).toHaveTextContent("Failed");
  });

  it("opens a run's full trace: steps, tools, arguments, results, verification, credits and model", async () => {
    const user = userEvent.setup();
    renderWithApi(<AgentSettingsPage />, { handlers: handlers() });
    const row = await screen.findByRole("button", { name: "Open the run: How did my latest post do?" });
    await user.click(row);
    const sheet = await screen.findByRole("dialog", { name: "Run" });
    const trace = await within(sheet).findByTestId("run-trace");
    expect(trace).toHaveTextContent("Priya Nair");
    expect(trace).toHaveTextContent("3 credits");
    expect(trace).toHaveTextContent("gemini-2.5-flash");
    expect(trace).toHaveTextContent("agent.v1");
    expect(trace).toHaveTextContent("Read only");
    expect(trace).toHaveTextContent("8.0 s");
    // The answer as the member saw it, with its citations.
    expect(within(trace).getByRole("link", { name: "Source 1: Post, Reel of 28 Sep" })).toHaveAttribute("href", "/w/maple/comments/po1");
    // Prepared actions and where they lead.
    expect(trace).toHaveTextContent("Schedule this message");
    expect(trace).toHaveTextContent("inbox/c1?schedule=1");

    const steps = within(trace).getAllByTestId("step-trace");
    expect(steps).toHaveLength(3);
    expect(steps[1]).toHaveTextContent("Comparing with 10 earlier posts at 24 hours");
    expect(steps[1]).toHaveTextContent("compare_posts · Read · 1.3 s · 2 attempts");
    expect(steps[1]).toHaveTextContent("Reach 4,120 vs median 2,900 (+42%)");
    await user.click(within(steps[1]).getByText("Arguments"));
    expect(within(steps[1]).getByText(/"baseline": "previous"/)).toBeVisible();
    expect(within(steps[1]).getByText(/"median": 2900/)).toBeInTheDocument();
    expect(steps[2]).toHaveAttribute("data-status", "failed");
    expect(steps[2]).toHaveTextContent("Comments on this post aren't analysed yet (insights_missing)");
    expect(steps[2]).toHaveTextContent("Not confirmed");
    expect(steps[2]).toHaveTextContent("Checked: comment analyses");
  });

  it("a failed run's trace names the error; the sheet closes and returns focus to its row", async () => {
    const user = userEvent.setup();
    renderWithApi(<AgentSettingsPage />, { handlers: handlers() });
    const row = await screen.findByRole("button", { name: "Open the run: Top posts this month" });
    await user.click(row);
    const sheet = await screen.findByRole("dialog", { name: "Run" });
    expect(await within(sheet).findByText("The AI didn't respond (ai_unavailable)")).toBeInTheDocument();
    expect(within(sheet).getByText("No steps ran.")).toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("button", { name: "Open the run: Top posts this month" })).toHaveFocus();
  });

  it("pages to older runs, reading further from the API when the loaded ones run out", async () => {
    const user = userEvent.setup();
    renderWithApi(<AgentSettingsPage />, { handlers: handlers([answered], "page2") });
    expect(await screen.findByRole("button", { name: "Open the run: How did my latest post do?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("button", { name: "Open the run: Oldest question" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open the run: How did my latest post do?" })).toBeNull();
    expect(screen.getByText(/Page 2/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(await screen.findByRole("button", { name: "Open the run: How did my latest post do?" })).toBeInTheDocument();
  });

  it("an empty history says what will appear", async () => {
    renderWithApi(<AgentSettingsPage />, { handlers: handlers([]) });
    expect(await screen.findByText("No questions yet")).toBeInTheDocument();
  });

  it("is for owners and admins; a member is pointed to their own questions", () => {
    renderWithApi(<AgentSettingsPage />, { handlers: handlers(), ws: { ...workspace, role: "agent" } });
    expect(screen.getByText("Run history is for owners and admins")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Ask Social Hood" })).toHaveAttribute("href", "/w/maple/ask");
  });
});

describe("run history search and filters (C-066)", () => {
  const partly = runDetail({ id: "r4", request: "Top posts this week", status: "partial" });
  const waiting = runDetail({ id: "r5", request: "Reply to everyone", status: "awaiting_approval" });
  const expired = runDetail({ id: "r6", request: "Old question", status: "expired" });
  const all = [answered, failed, partly, waiting, expired];

  function filtering() {
    return handlers(all, null, (call) => {
      const statuses = call.url.searchParams.getAll("status");
      const q = (call.url.searchParams.get("q") ?? "").toLowerCase();
      return all.filter(
        (run) => (statuses.length === 0 || statuses.includes(run.status)) && run.request.toLowerCase().includes(q),
      );
    });
  }

  const rows = () =>
    within(screen.getByRole("list", { name: "Runs" }))
      .getAllByRole("button")
      .map((row) => row.getAttribute("aria-label")?.replace("Open the run: ", ""));

  it("each chip asks the API for its statuses", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithApi(<AgentSettingsPage />, { handlers: filtering() });
    const chips = await screen.findByRole("radiogroup", { name: "Filter runs" });
    expect(within(chips).getAllByRole("radio").map((chip) => chip.textContent)).toEqual([
      "All",
      "Answered",
      "Action needed",
      "Failed",
    ]);
    await screen.findByRole("list", { name: "Runs" });
    expect(rows()).toHaveLength(5);

    await user.click(within(chips).getByRole("radio", { name: "Answered" }));
    await waitFor(() => expect(rows()).toEqual(["How did my latest post do?", "Top posts this week"]));
    await user.click(within(chips).getByRole("radio", { name: "Action needed" }));
    await waitFor(() => expect(rows()).toEqual(["Reply to everyone"]));
    await user.click(within(chips).getByRole("radio", { name: "Failed" }));
    await waitFor(() => expect(rows()).toEqual(["Top posts this month", "Old question"]));

    const statusSets = calls
      .filter((c) => c.path === "/v1/w/w1/agent/runs")
      .map((c) => c.url.searchParams.getAll("status").join(","));
    expect(statusSets).toEqual(["", "succeeded,partial", "awaiting_approval", "failed,expired"]);
  });

  it("search asks the API for the text once typing pauses; no match can show everything again", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithApi(<AgentSettingsPage />, { handlers: filtering() });
    await screen.findByRole("list", { name: "Runs" });
    await user.type(screen.getByRole("searchbox", { name: "Search runs" }), "top posts");
    await waitFor(() => expect(rows()).toEqual(["Top posts this month", "Top posts this week"]));
    const searched = calls.filter((c) => c.path === "/v1/w/w1/agent/runs").map((c) => c.url.searchParams.get("q"));
    expect(searched).toEqual([null, "top posts"]); // one request for the phrase, not one per key

    await user.clear(screen.getByRole("searchbox", { name: "Search runs" }));
    await user.type(screen.getByRole("searchbox", { name: "Search runs" }), "nothing like it");
    expect(await screen.findByText("No runs match")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show all runs" }));
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(screen.getByRole("searchbox", { name: "Search runs" })).toHaveValue("");
  });

  it("a row still opens the run's trace", async () => {
    const user = userEvent.setup();
    renderWithApi(<AgentSettingsPage />, { handlers: filtering() });
    await user.click(await screen.findByRole("button", { name: "Open the run: Top posts this month" }));
    const sheet = await screen.findByRole("dialog", { name: "Run" });
    expect(await within(sheet).findByText("The AI didn't respond (ai_unavailable)")).toBeInTheDocument();
  });
});
