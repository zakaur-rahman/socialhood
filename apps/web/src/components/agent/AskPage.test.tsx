import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetAskStore, useAskStore } from "@/lib/agent/store";
import type { AgentRunDetail, AgentThread } from "@/lib/api/types";
import { billingState, json, problem, renderWithApi, workspace, type Call } from "@/test/api";
import { agentThread, runDetail } from "@/test/agent";

import { AskPage } from "./AskPage";

vi.mock("next/navigation", () => ({
  usePathname: () => "/w/maple/ask",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const runs: AgentRunDetail[] = [
  runDetail({ id: "r1", thread_id: "t1", request: "Top posts this month", answer: "Your top post had 4,120 reach." }),
  runDetail({ id: "r2", thread_id: "t2", request: "Complaints this week", answer: "Mostly shipping costs." }),
];

const daysAgo = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString();

const defaultThreads: AgentThread[] = [
  agentThread({ id: "t2", title: "Complaints this week", last_run_at: new Date().toISOString() }),
  agentThread({ id: "t1", title: "Top posts this month", run_count: 3, last_status: "running", last_run_at: new Date().toISOString() }),
];

function handlers(threads: AgentThread[] = defaultThreads) {
  return {
    "GET /v1/w/:wid/billing": () => json(billingState()),
    "GET /v1/w/:wid/agent/threads": () => json({ items: threads, next_cursor: null }),
    "GET /v1/w/:wid/agent/runs": (call: Call) => {
      const threadId = call.url.searchParams.get("thread_id");
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const items = runs.filter((run) => run.thread_id === threadId).map(({ steps, plan, model, prompt_version, ...run }) => run);
      return json({ items, next_cursor: null });
    },
    "GET /v1/w/:wid/agent/runs/:id": (_: Call, p: Record<string, string>) => {
      const run = runs.find((item) => item.id === p.id);
      return run ? json(run) : problem(404, "not_found");
    },
  };
}

beforeEach(() => resetAskStore());

describe("The Ask page (FR-AGT-01)", () => {
  it("lists the member's threads; picking one shows its questions and answers", async () => {
    const user = userEvent.setup();
    renderWithApi(<AskPage />, { handlers: handlers() });
    expect(screen.getByRole("heading", { level: 1, name: "Ask Social Hood" })).toBeInTheDocument();
    const history = screen.getByRole("complementary", { name: "Thread history" });
    const threads = await within(history).findByRole("navigation", { name: "Threads" });
    const items = within(threads).getAllByRole("button");
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining("Complaints this week"),
      expect.stringContaining("Top posts this month"),
    ]);
    // The count shows only when a thread has more than one question; a working one spins.
    expect(items[0]).not.toHaveTextContent(/question/);
    expect(items[1]).toHaveTextContent("3 questions");
    expect(within(items[1]).getByLabelText("Working")).toBeInTheDocument();

    // A new thread to begin with: the welcome and its questions.
    expect(screen.getByRole("list", { name: "Suggested questions" })).toBeInTheDocument();
    await user.click(items[1]);
    expect(items[1]).toHaveAttribute("aria-current", "true");
    expect(items[1]).toHaveClass("bg-raised", "before:w-0.5", "before:bg-brand");
    expect(await screen.findByText("Your top post had 4,120 reach.")).toBeInTheDocument();
    expect(useAskStore.getState().threads.w1).toBe("t1");

    const newThread = within(history).getByRole("button", { name: "New thread" });
    expect(newThread).toHaveClass("w-full");
    await user.click(newThread);
    expect(await screen.findByRole("list", { name: "Suggested questions" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Ask Social Hood a question" })).toHaveFocus();
  });

  it("groups threads by Today, Yesterday, Previous 7 days and Older, one truncated line each", async () => {
    renderWithApi(<AskPage />, {
      handlers: handlers([
        agentThread({ id: "a", title: "Asked just now", last_run_at: new Date().toISOString() }),
        agentThread({ id: "b", title: "Asked yesterday", last_run_at: daysAgo(1) }),
        agentThread({ id: "c", title: "Asked four days ago", last_run_at: daysAgo(4) }),
        agentThread({ id: "d", title: "Asked last month", last_run_at: daysAgo(30) }),
      ]),
    });
    const threads = await screen.findByRole("navigation", { name: "Threads" });
    const groups = within(threads).getAllByRole("group");
    expect(groups.map((group) => group.getAttribute("aria-label"))).toEqual([
      "Today",
      "Yesterday",
      "Previous 7 days",
      "Older",
    ]);
    expect(within(groups[2]).getByRole("button")).toHaveTextContent("Asked four days ago");
    expect(within(groups[0]).getByText("Asked just now")).toHaveClass("truncate");
  });

  it("puts the conversation and the question box in one centred readable column", async () => {
    useAskStore.getState().setThread("w1", "t2");
    renderWithApi(<AskPage />, { handlers: handlers() });
    await screen.findByText("Mostly shipping costs.");
    const log = screen.getByRole("log", { name: "Conversation with Social Hood" });
    expect(log.firstElementChild).toHaveClass("mx-auto", "max-w-3xl");
    const box = screen.getByRole("textbox", { name: "Ask Social Hood a question" });
    expect(box.closest("form")?.parentElement).toHaveClass("mx-auto", "max-w-3xl");
  });

  it("the welcome offers a 2 × 2 grid of questions, one per area", () => {
    renderWithApi(<AskPage />, { handlers: handlers() });
    const prompts = screen.getByRole("list", { name: "Suggested questions" });
    expect(prompts).toHaveClass("grid", "sm:grid-cols-2");
    expect(within(prompts).getAllByRole("button")).toHaveLength(4);
  });

  it("shows the same thread as the panel", async () => {
    useAskStore.getState().setThread("w1", "t2");
    renderWithApi(<AskPage />, { handlers: handlers() });
    expect(await screen.findByText("Mostly shipping costs.")).toBeInTheDocument();
  });

  it("links admins to the run history; members don't get the link", () => {
    const { unmount } = renderWithApi(<AskPage />, { handlers: handlers() });
    for (const link of screen.getAllByRole("link", { name: "Run history" })) {
      expect(link).toHaveAttribute("href", "/w/maple/settings/agent");
    }
    unmount();
    renderWithApi(<AskPage />, { handlers: handlers(), ws: { ...workspace, role: "agent" } });
    expect(screen.queryByRole("link", { name: "Run history" })).toBeNull();
  });

  it("at 375 px the thread history is a menu and the page fills the screen below the top bar", async () => {
    const user = userEvent.setup();
    renderWithApi(<AskPage />, { handlers: handlers() });
    // It fills what the shell's <main> leaves under the top bar and any banner (UI-006), not 100dvh minus a constant.
    const page = screen.getByTestId("ask-page");
    expect(page).toHaveClass("flex-1", "min-h-0");
    expect(page).toHaveAttribute("data-shell-fill");
    // The column shows from 1024 px; below that the menu and New thread sit in the header.
    expect(screen.getByRole("complementary", { name: "Thread history" })).toHaveClass("hidden", "lg:flex");
    const header = screen.getByTestId("ask-header");
    const menu = within(header).getByRole("button", { name: "Threads" });
    expect(menu.parentElement).toHaveClass("lg:hidden");
    expect(within(header).getByRole("button", { name: "New thread" })).toHaveClass("size-8", "pointer-coarse:size-10");
    await user.click(menu);
    const menuContent = await screen.findByRole("menu");
    expect(within(menuContent).getByRole("menuitem", { name: "New thread" })).toBeInTheDocument();
    expect(within(menuContent).getByText("Today")).toBeInTheDocument();
    await user.click(within(menuContent).getByRole("menuitem", { name: /Complaints this week/ }));
    await waitFor(() => expect(screen.getByText("Mostly shipping costs.")).toBeInTheDocument());
  });
});
