import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetAskStore, useAskStore } from "@/lib/agent/store";
import type { AgentRunDetail } from "@/lib/api/types";
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

function handlers() {
  return {
    "GET /v1/w/:wid/billing": () => json(billingState()),
    "GET /v1/w/:wid/agent/threads": () =>
      json({
        items: [
          agentThread({ id: "t2", title: "Complaints this week", last_run_at: "2026-09-29T11:00:00Z" }),
          agentThread({ id: "t1", title: "Top posts this month", run_count: 3, last_status: "running" }),
        ],
        next_cursor: null,
      }),
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
    expect(items[1]).toHaveTextContent("3 questions");
    expect(within(items[1]).getByLabelText("Working")).toBeInTheDocument();

    // A new thread to begin with: the suggested questions.
    expect(screen.getByRole("list", { name: "Suggested questions" })).toBeInTheDocument();
    await user.click(items[1]);
    expect(items[1]).toHaveAttribute("aria-current", "true");
    expect(await screen.findByText("Your top post had 4,120 reach.")).toBeInTheDocument();
    expect(useAskStore.getState().threads.w1).toBe("t1");

    await user.click(within(history).getByRole("button", { name: "New thread" }));
    expect(await screen.findByRole("list", { name: "Suggested questions" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Ask Social Hood a question" })).toHaveFocus();
  });

  it("shows the same thread as the panel", async () => {
    useAskStore.getState().setThread("w1", "t2");
    renderWithApi(<AskPage />, { handlers: handlers() });
    expect(await screen.findByText("Mostly shipping costs.")).toBeInTheDocument();
  });

  it("links admins to the run history; members don't get the link", () => {
    const { unmount } = renderWithApi(<AskPage />, { handlers: handlers() });
    expect(screen.getByRole("link", { name: "Run history" })).toHaveAttribute("href", "/w/maple/settings/agent");
    unmount();
    renderWithApi(<AskPage />, { handlers: handlers(), ws: { ...workspace, role: "agent" } });
    expect(screen.queryByRole("link", { name: "Run history" })).toBeNull();
  });

  it("at 375 px the thread history is a menu and the page fills the screen below the top bar", async () => {
    const user = userEvent.setup();
    renderWithApi(<AskPage />, { handlers: handlers() });
    expect(screen.getByTestId("ask-page")).toHaveClass("h-[calc(100dvh-56px)]", "md:h-[calc(100dvh-32px)]");
    // The column shows from 1024 px; below that the menu and New thread sit in the header.
    expect(screen.getByRole("complementary", { name: "Thread history" })).toHaveClass("hidden", "lg:flex");
    const header = screen.getByRole("banner");
    const menu = within(header).getByRole("button", { name: "Threads" });
    expect(menu.parentElement).toHaveClass("lg:hidden");
    expect(within(header).getByRole("button", { name: "New thread" })).toHaveClass("size-10");
    await user.click(menu);
    await user.click(await screen.findByRole("menuitem", { name: /Complaints this week/ }));
    await waitFor(() => expect(screen.getByText("Mostly shipping costs.")).toBeInTheDocument());
  });
});
