import { screen, waitFor, within } from "@testing-library/react";
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

import { AskButton, AskRoot, PAGE_COMPOSER_ID } from "./AskPanel";

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
        created_at: `2026-09-29T11:0${created}:00Z`,
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
  it("offers the suggested prompts; one asks at once and starts a thread", async () => {
    const { posts } = setup();
    const { user, panel } = await openPanel();
    const prompts = within(panel).getByRole("list", { name: "Suggested questions" });
    expect(within(prompts).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "How did my latest post do?",
      "What are people complaining about this week?",
      "Which posts beat my average this month?",
    ]);
    await user.click(within(prompts).getByRole("button", { name: "What are people complaining about this week?" }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toEqual({ request: "What are people complaining about this week?" });
    const run = await within(panel).findByRole("article", { name: "Question: What are people complaining about this week?" });
    expect(await within(run).findByText(/Starting/)).toBeInTheDocument();
    expect(useAskStore.getState().threads.w1).toBe("new1");
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
    await within(run).findByText(/Starting/);

    emitRun(queryClient, { id: "new1", thread_id: "new1", status: "running", step_count: 0 });
    await within(run).findByText(/Reading your question/);
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
    expect(await within(steps).findByText("Looking up your latest post")).toBeInTheDocument();
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
    expect(await within(steps).findByText("Reel from 28 Sep, 26 hours old")).toBeInTheDocument();
    expect(within(steps).getByText("Comparing with 10 earlier posts at 24 hours")).toBeInTheDocument();
    // While it works: Cancel, and no question box sending.
    expect(within(run).getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Ask" })).toBeDisabled();

    // The event carries no answer; the run is fetched for it.
    state.runs.new1 = runDetail({
      ...state.runs.new1,
      status: "succeeded",
      answer: LATEST_POST_ANSWER,
      answer_refs: LATEST_POST_REFS,
      credits: 3,
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
    const sources = within(run).getByRole("list", { name: "Sources" });
    expect(within(sources).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "/w/maple/comments/po1",
      "/w/maple/comments/po0",
    ]);
    expect(within(run).queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(within(run).getByText("3 credits")).toBeInTheDocument();
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
    await user.click(within(run).getByRole("button", { name: "Reply to this comment" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/comments/po1");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("Cancel stops a working run; finished steps stay and it can be asked again", async () => {
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
    await user.click(await within(run).findByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/agent/runs/r1/cancel")).toBe(true));
    expect(await within(run).findByText("Cancelled")).toBeInTheDocument();
    expect(within(run).getByText(/You stopped this question/)).toBeInTheDocument();
    expect(within(run).getByRole("button", { name: "Ask again" })).toBeInTheDocument();
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

  it("finished runs show their steps on request", async () => {
    const user = userEvent.setup();
    setup({
      runs: { r1: runDetail({ answer: "Done.", steps: [agentStep({ label: "Looking up your latest post", summary: "Found it" })] }) },
    });
    useAskStore.getState().setThread("w1", "r1");
    const { panel } = await openPanel();
    const toggle = await within(panel).findByRole("button", { name: "Show steps" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(await within(panel).findByText("Looking up your latest post")).toBeInTheDocument();
    expect(within(panel).getByText("Found it")).toBeInTheDocument();
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
    for (const link of within(panel).getAllByRole("link", { name: /Reel of/ }).filter((a) => a.closest("ol"))) {
      expect(link).toHaveClass("min-h-10");
    }
  });
});
