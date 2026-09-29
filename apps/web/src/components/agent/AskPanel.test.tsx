import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetAgentHandoff } from "@/lib/agent/handoff";
import { resetAskStore, useAskStore } from "@/lib/agent/store";
import type { AgentRun, AgentRunCreate, AgentRunDetail, AgentThread, BillingState, WorkspaceSummary } from "@/lib/api/types";
import { billingState, json, problem, renderWithApi, workspace, type Call } from "@/test/api";
import {
  agentStep,
  agentThread,
  draftCard,
  emitRun,
  emitStep,
  LATEST_POST_ANSWER,
  LATEST_POST_REFS,
  replyCard,
  runDetail,
  scheduleCard,
} from "@/test/agent";

import { fitTextarea } from "./AskComposer";
import { AskButton, AskRoot, PAGE_COMPOSER_ID } from "./AskPanel";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ pathname: "/w/maple/home", push: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  useSearchParams: () => new URLSearchParams(),
}));

type Server = {
  runs: Record<string, AgentRunDetail>;
  threads: AgentThread[];
  billing?: BillingState;
  create?: (call: Call) => Response;
};

function summaryOf(run: AgentRunDetail): AgentRun {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { steps, plan, model, prompt_version, ...rest } = run;
  return rest;
}

function handlers(server: Server) {
  let created = 0;
  return {
    "GET /v1/w/:wid/billing": () => json(server.billing ?? billingState()),
    "GET /v1/w/:wid/agent/threads": () => json({ items: server.threads, next_cursor: null }),
    "GET /v1/w/:wid/agent/runs": (call: Call) => {
      const threadId = call.url.searchParams.get("thread_id");
      const items = Object.values(server.runs)
        .filter((run) => !threadId || run.thread_id === threadId)
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map(summaryOf);
      return json({ items, next_cursor: null });
    },
    "GET /v1/w/:wid/agent/runs/:id": (_: Call, p: Record<string, string>) =>
      server.runs[p.id] ? json(server.runs[p.id]) : problem(404, "not_found"),
    "POST /v1/w/:wid/agent/runs": (call: Call) => {
      if (server.create) return server.create(call);
      created += 1;
      const body = call.body as AgentRunCreate;
      const id = `new${created}`;
      const run = runDetail({
        id,
        thread_id: body.thread_id ?? id,
        request: body.request,
        status: "queued",
        started_at: null,
        // Just asked: the seconds so far count from here.
        created_at: new Date(Date.now() + created).toISOString(),
      });
      server.runs[id] = run;
      return json(summaryOf(run), 202);
    },
    "POST /v1/w/:wid/agent/runs/:id/cancel": (_: Call, p: Record<string, string>) => {
      server.runs[p.id] = { ...server.runs[p.id], status: "cancelled", completed_at: "2026-09-29T11:05:00Z" };
      return json(summaryOf(server.runs[p.id]));
    },
  };
}

function setup(server: Partial<Server> = {}, ws: WorkspaceSummary = workspace) {
  const state: Server = { runs: {}, threads: [], ...server };
  const view = renderWithApi(
    <>
      <AskButton variant="sidebar" />
      <AskRoot />
    </>,
    { handlers: handlers(state), ws },
  );
  const posts = () => view.calls.filter((c) => c.method === "POST" && c.path === "/v1/w/w1/agent/runs");
  return { ...view, state, posts };
}

async function openPanel() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Ask Social Hood" }));
  const panel = await screen.findByRole("dialog", { name: "Ask Social Hood" });
  return { user, panel };
}

beforeEach(() => {
  resetAskStore();
  resetAgentHandoff();
  nav.pathname = "/w/maple/home";
  nav.push.mockReset();
});

describe("Ask Social Hood panel: opening and closing (FR-AGT-01, UX-A11Y-02)", () => {
  it("opens from its button with the question box focused, and Esc closes it and returns focus", async () => {
    setup();
    const { user, panel } = await openPanel();
    expect(within(panel).getByRole("textbox", { name: "Ask Social Hood a question" })).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("button", { name: "Ask Social Hood" })).toHaveFocus();
  });

  it("the Close button closes it", async () => {
    setup();
    const { user, panel } = await openPanel();
    await user.click(within(panel).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("Ctrl K and ⌘ K open and close it anywhere; K alone doesn't", async () => {
    setup();
    expect(screen.getByRole("button", { name: "Ask Social Hood" })).toHaveAttribute("aria-keyshortcuts", "Control+K Meta+K");
    const user = userEvent.setup();
    await user.keyboard("k");
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.keyboard("{Control>}k{/Control}");
    expect(await screen.findByRole("dialog", { name: "Ask Social Hood" })).toBeInTheDocument();
    await user.keyboard("{Control>}k{/Control}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await user.keyboard("{Meta>}k{/Meta}");
    expect(await screen.findByRole("dialog", { name: "Ask Social Hood" })).toBeInTheDocument();
  });

  it("leaves another open dialog alone", async () => {
    setup();
    const other = document.createElement("div");
    other.setAttribute("role", "dialog");
    document.body.appendChild(other);
    await userEvent.setup().keyboard("{Control>}k{/Control}");
    expect(screen.queryByRole("dialog", { name: "Ask Social Hood" })).toBeNull();
    other.remove();
  });

  it("on the Ask page, the shortcut and the button focus that page's question box instead", async () => {
    nav.pathname = "/w/maple/ask";
    setup();
    const box = document.createElement("textarea");
    box.id = PAGE_COMPOSER_ID;
    document.body.appendChild(box);
    const user = userEvent.setup();
    await user.keyboard("{Control>}k{/Control}");
    expect(box).toHaveFocus();
    box.blur();
    await user.click(screen.getByRole("button", { name: "Ask Social Hood" }));
    expect(box).toHaveFocus();
    expect(screen.queryByRole("dialog")).toBeNull();
    box.remove();
  });
});

describe("Asking (FR-AGT-01, agent-architecture.html §12)", () => {
  it("a new thread welcomes the member and offers a question per area; one asks at once and starts a thread", async () => {
    const { posts } = setup();
    const { user, panel } = await openPanel();
    const welcome = within(panel).getByTestId("ask-welcome");
    expect(within(welcome).getByRole("heading", { name: "What would you like to know?" })).toBeInTheDocument();
    const prompts = within(panel).getByRole("list", { name: "Suggested questions" });
    // The panel lists them; the page shows a 2 × 2 grid (AskPage.test).
    expect(prompts).toHaveClass("flex-col");
    expect(within(prompts).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "How did my latest post do?",
      "What are people complaining about this week?",
      "Which conversations need a reply today?",
      "Which automation sent the most DMs this week?",
    ]);
    await user.click(within(prompts).getByRole("button", { name: "What are people complaining about this week?" }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toEqual({ request: "What are people complaining about this week?" });
    const run = await within(panel).findByRole("article", { name: "Question: What are people complaining about this week?" });
    expect(await within(run).findByText("Starting…")).toBeInTheDocument();
    expect(useAskStore.getState().threads.w1).toBe("new1");
  });

  it("shows the question in a neutral bubble with its time on hover, and the answer beside the Social Hood mark", async () => {
    setup({ runs: { r1: runDetail({ answer: "Your latest reel did well." }) } });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    const run = await within(panel).findByRole("article", { name: "Question: How did my latest post do?" });
    const bubble = within(run).getByText("How did my latest post do?");
    expect(bubble).toHaveClass("bg-raised", "rounded-2xl", "max-w-[80%]");
    expect(bubble).toHaveAttribute("title", expect.stringMatching(/15:30$/));
    const time = run.querySelector("time");
    expect(time).toHaveAttribute("dateTime", "2026-09-29T10:00:00Z");
    expect(time).toHaveClass("opacity-0", "group-hover/run:opacity-100", "group-focus-within/run:opacity-100");
    // No card around the answer: 15 px type on 28 px lines.
    expect(within(run).getByTestId("answer")).toHaveClass("text-[15px]", "leading-7");
    expect(within(run).getByTestId("run-result").className).not.toMatch(/\bborder\b/);
  });

  it("a queued run that doesn't start within 20 seconds says it's waiting", async () => {
    setup({
      runs: { r1: runDetail({ status: "queued", started_at: null, created_at: new Date(Date.now() - 30_000).toISOString() }) },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    const run = await within(panel).findByRole("article");
    expect(await within(run).findByText("Waiting to start…")).toBeInTheDocument();
    expect(within(run).getByTestId("elapsed")).toHaveTextContent(/^3\d s$/);
  });

  it("Enter asks the typed question; Shift+Enter adds a line", async () => {
    const { posts } = setup();
    const { user, panel } = await openPanel();
    const box = within(panel).getByRole("textbox", { name: "Ask Social Hood a question" });
    await user.type(box, "Top posts{Shift>}{Enter}{/Shift}this month{Enter}");
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toEqual({ request: "Top posts\nthis month" });
    await waitFor(() => expect(box).toHaveValue(""));
  });

  it("shows live steps in plain words while the run works, then the answer with its table and citations", async () => {
    const { state, queryClient, calls } = setup();
    const { user, panel } = await openPanel();
    await user.click(within(panel).getByRole("button", { name: "How did my latest post do?" }));
    const run = await within(panel).findByRole("article", { name: "Question: How did my latest post do?" });
    await within(run).findByText("Starting…");
    expect(within(run).getByTestId("elapsed")).toHaveTextContent(/^\d+ s$/);
    expect(within(run).getByTestId("elapsed")).toHaveAttribute("aria-hidden", "true");

    emitRun(queryClient, { id: "new1", thread_id: "new1", status: "running", step_count: 0 });
    await within(run).findByText("Reading your question…");
    emitStep(queryClient, "new1", {
      id: "s1",
      ordinal: 0,
      kind: "tool",
      tool: "get_latest_post",
      label: "Looking up your latest post",
      status: "running",
      summary: null,
      latency_ms: 0,
    });
    const steps = within(run).getByRole("list", { name: "Steps" });
    // The step it is on: a shimmering label.
    const current = await within(steps).findByText("Looking up your latest post…");
    expect(current).toHaveClass("text-shimmer");
    expect(steps).toHaveAttribute("aria-live", "polite");
    emitStep(queryClient, "new1", {
      id: "s1",
      ordinal: 0,
      kind: "tool",
      tool: "get_latest_post",
      label: "Looking up your latest post",
      status: "succeeded",
      summary: "Reel from 28 Sep, 26 hours old",
      latency_ms: 300,
    });
    emitStep(queryClient, "new1", {
      id: "s2",
      ordinal: 1,
      kind: "tool",
      tool: "compare_posts",
      label: "Comparing with 10 earlier posts at 24 hours",
      status: "running",
      summary: null,
      latency_ms: 0,
    });
    // Finished steps sit above the current one, with a check.
    expect(await within(steps).findByText("Reel from 28 Sep, 26 hours old")).toBeInTheDocument();
    expect(within(steps).getByText("Looking up your latest post").closest("li")).toHaveAttribute("data-status", "succeeded");
    expect(within(steps).getByText("Comparing with 10 earlier posts at 24 hours…")).toHaveClass("text-shimmer");
    // While it works the member can type; the button stops the run instead of asking.
    const box = within(panel).getByRole("textbox", { name: "Ask Social Hood a question" });
    await user.type(box, "and last week?");
    expect(box).toHaveValue("and last week?");
    expect(within(panel).getByRole("button", { name: "Stop" })).toBeEnabled();
    expect(within(panel).queryByRole("button", { name: "Ask" })).toBeNull();
    expect(within(panel).queryByText(/still working/)).toBeNull();
    await user.keyboard("{Enter}");
    expect(calls.filter((c) => c.method === "POST" && c.path === "/v1/w/w1/agent/runs")).toHaveLength(1);

    // The event carries no answer; the run is fetched for it.
    state.runs.new1 = runDetail({
      ...state.runs.new1,
      status: "succeeded",
      answer: LATEST_POST_ANSWER,
      answer_refs: LATEST_POST_REFS,
      credits: 3,
      started_at: "2026-09-29T11:01:03Z",
      completed_at: "2026-09-29T11:01:09Z",
      steps: [agentStep({ id: "s1" }), agentStep({ id: "s2", ordinal: 1, tool: "compare_posts", label: "Comparing with 10 earlier posts at 24 hours" })],
    });
    const fetchesBefore = calls.filter((c) => c.path === "/v1/w/w1/agent/runs/new1").length;
    emitRun(queryClient, { id: "new1", thread_id: "new1", status: "succeeded", step_count: 2 }, true);

    const answer = await within(run).findByTestId("answer");
    expect(calls.filter((c) => c.path === "/v1/w/w1/agent/runs/new1").length).toBeGreaterThan(fetchesBefore);
    expect(within(answer).getByText("better than usual").tagName).toBe("STRONG");
    const table = within(answer).getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Metric", "This reel", "Median of 10"]);
    expect(within(table).getByRole("cell", { name: "4,120" })).toHaveClass("text-right");
    // The time range and sample size, as the answer states them (FR-AGT-04).
    expect(within(answer).getByText("Time range: 26 Sep to 28 Sep · 10 earlier reels compared.")).toBeInTheDocument();
    expect(within(answer).getByRole("link", { name: "Source 1: Post, Reel of 28 Sep" })).toHaveAttribute("href", "/w/maple/comments/po1");
    expect(within(answer).getByRole("link", { name: "Source 2: Post, Reel of 20 Sep" })).toHaveAttribute("href", "/w/maple/comments/po0");
    // Sources: a wrap of chips, "1 · Reel of 28 Sep".
    const sources = within(run).getByRole("list", { name: "Sources" });
    expect(sources).toHaveClass("flex", "flex-wrap");
    expect(within(sources).getAllByRole("link").map((a) => [a.getAttribute("href"), a.textContent])).toEqual([
      ["/w/maple/comments/po1", "1·Post: Reel of 28 Sep"],
      ["/w/maple/comments/po0", "2·Post: Reel of 20 Sep"],
    ]);
    // One line at the top: how long it worked and how many steps; the steps on request.
    expect(within(run).getByTestId("steps-toggle")).toHaveTextContent("Worked for 6 s · 2 steps");
    expect(within(run).getByTestId("steps-toggle")).toHaveAttribute("aria-expanded", "false");
    // Copy and the credits under the answer; Ask is back.
    const actions = within(run).getByTestId("answer-actions");
    expect(within(actions).getByRole("button", { name: "Copy answer" })).toBeInTheDocument();
    expect(actions).toHaveTextContent("3 credits");
    expect(within(panel).queryByRole("button", { name: "Stop" })).toBeNull();
    expect(within(panel).getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("a citation pill names its record on hover or focus", async () => {
    setup({ runs: { r1: runDetail({ answer: LATEST_POST_ANSWER, answer_refs: LATEST_POST_REFS }) } });
    useAskStore.getState().setThread("w1", "r1");
    const { user, panel } = await openPanel();
    const pill = await within(panel).findByRole("link", { name: "Source 1: Post, Reel of 28 Sep" });
    expect(pill).toHaveTextContent(/^1$/);
    expect(pill).toHaveClass("rounded-full");
    await user.hover(pill);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Post · Reel of 28 Sep");
  });

  it("Copy puts the answer on the clipboard as plain text, without the citation markers", async () => {
    setup({ runs: { r1: runDetail({ answer: LATEST_POST_ANSWER, answer_refs: LATEST_POST_REFS }) } });
    useAskStore.getState().setThread("w1", "r1");
    const { user, panel } = await openPanel();
    await user.click(await within(panel).findByRole("button", { name: "Copy answer" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Copied"));
    const copied = await navigator.clipboard.readText();
    expect(copied).toBe(
      [
        "Your latest reel is doing better than usual. At 24 hours it reached 4,120 people, 42% above the median of your previous 10 reels.",
        "",
        "Metric\tThis reel\tMedian of 10",
        "Reach\t4,120\t2,900",
        "Engagement rate\t6.1%\t4.4%",
        "",
        "Time range: 26 Sep to 28 Sep · 10 earlier reels compared.",
      ].join("\n"),
    );
  });

  it("under the latest answer, follow-up questions from what it cited ask in the same thread", async () => {
    const { posts } = setup({
      runs: {
        r0: runDetail({ id: "r0", thread_id: "t1", request: "Earlier", answer: "Earlier answer [1].", answer_refs: LATEST_POST_REFS, created_at: "2026-09-29T09:00:00Z" }),
        r1: runDetail({ id: "r1", thread_id: "t1", answer: "Your latest reel did well [1].", answer_refs: LATEST_POST_REFS }),
      },
    });
    useAskStore.getState().setThread("w1", "t1");
    const { user, panel } = await openPanel();
    await within(panel).findByText(/Earlier answer/);
    const followUps = within(panel).getAllByRole("list", { name: "Follow-up questions" });
    // Only under the latest answer.
    expect(followUps).toHaveLength(1);
    expect(within(panel).getAllByRole("article")[1]).toContainElement(followUps[0]);
    expect(within(followUps[0]).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Show the negative comments on this post",
      "Compare it with my previous post",
    ]);
    await user.click(within(followUps[0]).getByRole("button", { name: "Compare it with my previous post" }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toEqual({ request: "Compare it with my previous post", thread_id: "t1" });
  });

  it("a citation closes the panel on its way to the record", async () => {
    setup({
      runs: { r1: runDetail({ answer: "Your top post [1].", answer_refs: [{ kind: "conversation", id: "c1", label: "Priya Nair" }] }) },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    const link = await within(panel).findByRole("link", { name: "Source 1: Conversation, Priya Nair" });
    expect(link).toHaveAttribute("href", "/w/maple/inbox/c1");
    link.addEventListener("click", (event) => event.preventDefault());
    await userEvent.click(link);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("shows each prepared action; opening one closes the panel and goes to its screen (FR-AGT-03)", async () => {
    setup({
      runs: {
        r1: runDetail({
          answer: "Priya's window closes soon. I prepared the message and a reply.",
          action_cards: [scheduleCard(), replyCard(), draftCard()],
        }),
      },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { user, panel } = await openPanel();
    const run = await within(panel).findByRole("article");
    expect(await within(run).findByRole("region", { name: "Scheduled message" })).toBeInTheDocument();
    expect(within(run).getByRole("region", { name: "Comment reply" })).toBeInTheDocument();
    expect(within(run).getByRole("region", { name: "Automation draft" })).toBeInTheDocument();
    await user.click(within(run).getByRole("button", { name: "Open: Reply to this comment" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/comments/po1");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("Stop cancels a working run; finished steps stay and it can be asked again", async () => {
    const { calls } = setup({
      runs: {
        r1: runDetail({
          status: "running",
          steps: [agentStep({ id: "s1", label: "Looking up your latest post", status: "succeeded", summary: "Found it" })],
        }),
      },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { user, panel } = await openPanel();
    const run = await within(panel).findByRole("article");
    // Between steps it says it's working on it.
    expect(await within(run).findByText("Working on it…")).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/agent/runs/r1/cancel")).toBe(true));
    expect(await within(run).findByText("Cancelled")).toBeInTheDocument();
    expect(within(run).getByText(/You stopped this question/)).toBeInTheDocument();
    expect(within(run).getByRole("button", { name: "Ask again" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Ask" })).toBeInTheDocument();
  });
});

describe("Runs that didn't answer (FR-AGT-06)", () => {
  it("a failed run says so, and Try again asks the same question in the same thread", async () => {
    const { posts } = setup({
      runs: { r1: runDetail({ status: "failed", error: { code: "ai_unavailable", message: "The AI didn't respond" } }) },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { user, panel } = await openPanel();
    const alert = await within(panel).findByRole("alert");
    expect(alert).toHaveTextContent("This question didn't get an answer");
    expect(alert).toHaveTextContent("The AI didn't respond");
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toEqual({ request: "How did my latest post do?", thread_id: "r1" });
  });

  it("a run that ran out of credits says so, with Upgrade for owners", async () => {
    setup({
      runs: {
        r1: runDetail({
          status: "partial",
          answer: "Your latest reel reached 4,120 people [1].",
          answer_refs: LATEST_POST_REFS,
          error: { code: "quota_exceeded", message: "You've used all 5,000 AI credits for this month." },
        }),
      },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    const notice = await within(panel).findByRole("alert");
    expect(notice).toHaveTextContent("Out of AI credits");
    expect(notice).toHaveTextContent("You've used all 5,000 AI credits for this month.");
    expect(within(notice).getByRole("link", { name: "Upgrade" })).toHaveAttribute("href", "/w/maple/settings/billing");
    // What was done is still shown.
    expect(within(panel).getByTestId("answer")).toHaveTextContent("Your latest reel reached 4,120 people");
  });

  it("asking with no credits left (402) keeps the question and says when they reset; agents get no Upgrade", async () => {
    setup(
      { create: () => problem(402, "quota_exceeded", "You've used all 5,000 AI credits for this month.") },
      { ...workspace, role: "agent" },
    );
    const { user, panel } = await openPanel();
    const box = within(panel).getByRole("textbox", { name: "Ask Social Hood a question" });
    await user.type(box, "Top posts{Enter}");
    const alert = await within(panel).findByRole("alert");
    expect(alert).toHaveTextContent("You've used all 5,000 AI credits for this month.");
    expect(within(alert).queryByRole("link", { name: "Upgrade" })).toBeNull();
    expect(box).toHaveValue("Top posts");
  });

  it("with the credits used up, the question box explains and doesn't send", async () => {
    setup({
      billing: billingState({ usage: [{ metric: "ai_credits", used: 5000, limit: 5000, period_end: "2026-10-01" }] }),
    });
    const { user, panel } = await openPanel();
    expect(await within(panel).findByText(/You've used all 5,000 AI credits for this month. They reset on 1 Oct./)).toBeInTheDocument();
    await user.type(within(panel).getByRole("textbox", { name: "Ask Social Hood a question" }), "Top posts");
    expect(within(panel).getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("a partial answer says some steps didn't finish", async () => {
    setup({ runs: { r1: runDetail({ status: "partial", answer: "Reach was 4,120. Sentiment isn't available yet." }) } });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    expect(await within(panel).findByText("Some steps didn't finish. The answer says what's missing.")).toBeInTheDocument();
    expect(within(panel).getByTestId("answer")).toHaveTextContent("Sentiment isn't available yet.");
  });

  it("a finished run's one-line disclosure says how long it worked and opens its steps", async () => {
    const user = userEvent.setup();
    setup({
      runs: {
        r1: runDetail({
          answer: "Done.",
          started_at: "2026-09-29T10:00:01Z",
          completed_at: "2026-09-29T10:00:09Z",
          steps: [agentStep({ label: "Looking up your latest post", summary: "Found it" })],
        }),
      },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    const toggle = await within(panel).findByRole("button", { name: "Worked for 8 s" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(panel).queryByRole("list", { name: "Steps" })).toBeNull();
    await user.click(toggle);
    expect(await within(panel).findByText("Looking up your latest post")).toBeInTheDocument();
    expect(within(panel).getByText("Found it")).toBeInTheDocument();
    expect(toggle).toHaveTextContent("Worked for 8 s · 1 step");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("without a start and end it doesn't guess a duration", async () => {
    setup({ runs: { r1: runDetail({ answer: "Done.", completed_at: null }) } });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    expect(await within(panel).findByTestId("steps-toggle")).toHaveTextContent(/^Steps$/);
  });

  it("the notices are compact and inline, not cards", async () => {
    setup({ runs: { r1: runDetail({ status: "cancelled" }) } });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    const notice = await within(panel).findByRole("status");
    expect(notice).toHaveAttribute("data-outcome", "cancelled");
    expect(notice).toHaveClass("rounded-lg", "px-3", "py-2");
  });

  it("an expired run says so", async () => {
    setup({ runs: { r1: runDetail({ status: "expired" }) } });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    expect(await within(panel).findByText("This question waited too long and stopped.")).toBeInTheDocument();
  });
});

describe("Threads (FR-AGT-01)", () => {
  it("continues a thread: its questions show oldest first and the next one carries its id", async () => {
    const { posts } = setup({
      runs: {
        r1: runDetail({ id: "r1", thread_id: "t1", request: "First question", answer: "First answer", created_at: "2026-09-29T10:00:00Z" }),
        r2: runDetail({ id: "r2", thread_id: "t1", request: "Second question", answer: "Second answer", created_at: "2026-09-29T10:05:00Z" }),
      },
    });
    useAskStore.getState().setThread("w1", "t1");
    const { user, panel } = await openPanel();
    await within(panel).findByText("Second answer");
    expect(within(panel).getAllByRole("article").map((a) => a.getAttribute("aria-label"))).toEqual([
      "Question: First question",
      "Question: Second question",
    ]);
    await user.type(within(panel).getByRole("textbox", { name: "Ask Social Hood a question" }), "And the third?{Enter}");
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toEqual({ request: "And the third?", thread_id: "t1" });
    expect(await within(panel).findByRole("article", { name: "Question: And the third?" })).toBeInTheDocument();
  });

  it("New thread starts fresh; the Threads menu goes back to an earlier one", async () => {
    setup({
      runs: {
        r1: runDetail({ id: "r1", thread_id: "t1", request: "Earlier question", answer: "Earlier answer" }),
      },
      threads: [agentThread({ id: "t1", title: "Earlier question" })],
    });
    useAskStore.getState().setThread("w1", "t1");
    const { user, panel } = await openPanel();
    await within(panel).findByText("Earlier answer");
    await user.click(within(panel).getByRole("button", { name: "New thread" }));
    expect(await within(panel).findByRole("list", { name: "Suggested questions" })).toBeInTheDocument();
    expect(within(panel).queryByText("Earlier answer")).toBeNull();

    await user.click(within(panel).getByRole("button", { name: "Threads" }));
    await user.click(await screen.findByRole("menuitem", { name: /Earlier question/ }));
    expect(await within(panel).findByText("Earlier answer")).toBeInTheDocument();
  });

  it("links to the full Ask page", async () => {
    setup();
    const { panel } = await openPanel();
    expect(within(panel).getByRole("link", { name: "Open the Ask page" })).toHaveAttribute("href", "/w/maple/ask");
  });
});

describe("Layout at 375 px (UX-A11Y-05)", () => {
  it("fills the phone screen and is a 420 px side sheet from 768 px, with 40 px targets on phones", async () => {
    setup({
      runs: { r1: runDetail({ answer: LATEST_POST_ANSWER, answer_refs: LATEST_POST_REFS }) },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    expect(panel).toHaveClass("fixed", "inset-0", "md:left-auto", "md:w-[420px]");
    for (const name of ["New thread", "Threads", "Close"]) {
      expect(within(panel).getByRole("button", { name })).toHaveClass("size-10");
    }
    expect(within(panel).getByRole("button", { name: "Ask" })).toHaveClass("size-10");
    // Wide tables scroll inside the answer, never the page.
    const table = await within(panel).findByRole("table");
    expect(table.closest('[role="region"]')).toHaveClass("overflow-x-auto", "max-w-full");
    for (const link of within(within(panel).getByRole("list", { name: "Sources" })).getAllByRole("link")) {
      expect(link).toHaveClass("min-h-10", "md:min-h-7");
    }
    expect(within(panel).getByRole("button", { name: "Copy answer" })).toHaveClass("min-h-10");
    for (const button of within(within(panel).getByRole("list", { name: "Follow-up questions" })).getAllByRole("button")) {
      expect(button).toHaveClass("min-h-10");
    }
    // The question box keeps clear of the phone's home indicator.
    const box = within(panel).getByRole("textbox", { name: "Ask Social Hood a question" });
    expect(box.closest("form")?.parentElement).toHaveClass("pb-[calc(env(safe-area-inset-bottom)+0.75rem)]");
  });
});

describe("The question box", () => {
  it("is one rounded field with the send button inside, and never shows scroll arrows below its limit", async () => {
    setup();
    const { panel } = await openPanel();
    const box = within(panel).getByRole("textbox", { name: "Ask Social Hood a question" });
    const field = box.parentElement!;
    expect(field).toHaveClass("rounded-2xl", "border", "bg-field", "focus-within:ring-3");
    expect(field).toContainElement(within(panel).getByRole("button", { name: "Ask" }));
    expect(box).toHaveClass("overflow-y-hidden", "resize-none");
    expect(box.style.overflowY).toBe("hidden");
    // The desktop hint, for mouse and trackpad users.
    expect(within(panel).getByText("Enter to ask · Shift+Enter for a new line")).toHaveClass("hidden", "pointer-fine:block");
  });

  it("fits its text, counting the border that scrollHeight leaves out, and scrolls only past 160 px", () => {
    const el = document.createElement("textarea");
    const size = (scroll: number, offset: number, client: number) => {
      Object.defineProperty(el, "scrollHeight", { configurable: true, value: scroll });
      Object.defineProperty(el, "offsetHeight", { configurable: true, value: offset });
      Object.defineProperty(el, "clientHeight", { configurable: true, value: client });
    };
    size(34, 36, 34); // one line: 34 px of content and padding, 2 px of border
    fitTextarea(el);
    expect(el.style.height).toBe("36px");
    expect(el.style.overflowY).toBe("hidden");
    size(120, 36, 34);
    fitTextarea(el);
    expect(el.style.height).toBe("122px");
    expect(el.style.overflowY).toBe("hidden");
    size(300, 36, 34);
    fitTextarea(el);
    expect(el.style.height).toBe("160px");
    expect(el.style.overflowY).toBe("auto");
  });
});

describe("Scrolling", () => {
  it("offers Jump to latest when the member has scrolled up, and goes to the end", async () => {
    setup({
      runs: {
        r1: runDetail({ id: "r1", thread_id: "t1", answer: "First answer", created_at: "2026-09-29T10:00:00Z" }),
        r2: runDetail({ id: "r2", thread_id: "t1", request: "Second question", answer: "Second answer", created_at: "2026-09-29T10:05:00Z" }),
      },
    });
    useAskStore.getState().setThread("w1", "t1");
    const { user, panel } = await openPanel();
    await within(panel).findByText("Second answer");
    const log = within(panel).getByRole("log", { name: "Conversation with Social Hood" });
    Object.defineProperty(log, "scrollHeight", { configurable: true, value: 2000 });
    Object.defineProperty(log, "clientHeight", { configurable: true, value: 500 });
    expect(within(panel).queryByRole("button", { name: "Jump to latest" })).toBeNull();

    log.scrollTop = 200;
    fireEvent.scroll(log);
    const jump = await within(panel).findByRole("button", { name: "Jump to latest" });
    await user.click(jump);
    expect(log.scrollTop).toBe(2000);
    expect(within(panel).queryByRole("button", { name: "Jump to latest" })).toBeNull();

    // Near the end, it isn't offered.
    log.scrollTop = 1450;
    fireEvent.scroll(log);
    expect(within(panel).queryByRole("button", { name: "Jump to latest" })).toBeNull();
  });
});
