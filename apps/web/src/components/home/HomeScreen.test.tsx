import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import type { ChecklistStep, Overview, SentimentSplit } from "@/lib/api/types";
import { json, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { HomeScreen } from "./HomeScreen";

const steps = (connected: boolean): ChecklistStep[] => [
  { key: "connect_account", done: connected },
  { key: "add_knowledge", done: false },
  { key: "choose_ai_mode", done: false },
  { key: "create_automation", done: false },
];

const nothing: SentimentSplit = {
  total: 0,
  analysed: 0,
  positive: 0,
  neutral: 0,
  negative: 0,
  spam: 0,
  positive_pct: null,
  neutral_pct: null,
  negative_pct: null,
};

const quietPeriod = (since: string, until: string) => ({
  since,
  until,
  messages_received: 0,
  conversations: 0,
  conversations_replied: 0,
  reply_rate: null,
  handled_by_ai: 0,
  handled_by_ai_rate: null,
  first_responses: 0,
  median_first_response_s: null,
  comments_received: 0,
});

/** A new workspace: nothing connected, nothing counted. */
function empty(overrides: Partial<Overview> = {}): Overview {
  return {
    range: "7d",
    timezone: "Asia/Kolkata",
    checklist: { dismissed: false, completed: 0, steps: steps(false) },
    needs_reply: 0,
    needs_you: 0,
    knowledge_gaps_open: 0,
    top_questions: [],
    accounts_needing_attention: [],
    messages_today: 0,
    current: quietPeriod("2026-09-24", "2026-09-30"),
    previous: quietPeriod("2026-09-17", "2026-09-23"),
    top_intents: [],
    message_sentiment: nothing,
    comment_sentiment: nothing,
    top_posts: [],
    ...overrides,
  };
}

/** The seed of the API's test (tests/integration/test_overview.py), as the API returns it. */
function busy(overrides: Partial<Overview> = {}): Overview {
  return empty({
    checklist: { dismissed: false, completed: 1, steps: steps(true) },
    needs_reply: 2,
    needs_you: 1,
    knowledge_gaps_open: 2,
    top_questions: [
      { topic: "Do you ship to Dubai?", asked: 5 },
      { topic: "Eggless options", asked: 2 },
    ],
    accounts_needing_attention: [
      { id: "a2", platform: "instagram", username: "maple.outlet", status: "needs_reconnect" },
    ],
    messages_today: 2,
    current: {
      since: "2026-09-24",
      until: "2026-09-30",
      messages_received: 9,
      conversations: 8,
      conversations_replied: 5,
      reply_rate: 62.5,
      handled_by_ai: 2,
      handled_by_ai_rate: 40,
      first_responses: 4,
      median_first_response_s: 465,
      comments_received: 4,
    },
    previous: {
      since: "2026-09-17",
      until: "2026-09-23",
      messages_received: 12,
      conversations: 2,
      conversations_replied: 1,
      reply_rate: 50,
      handled_by_ai: 0,
      handled_by_ai_rate: 0,
      first_responses: 1,
      median_first_response_s: 3600,
      comments_received: 3,
    },
    top_intents: [
      { intent: "pricing", count: 3 },
      { intent: "complaint", count: 1 },
      { intent: "feedback", count: 1 },
    ],
    message_sentiment: {
      total: 9,
      analysed: 8,
      positive: 4,
      neutral: 1,
      negative: 2,
      spam: 1,
      positive_pct: 57.1,
      neutral_pct: 14.3,
      negative_pct: 28.6,
    },
    comment_sentiment: {
      total: 4,
      analysed: 3,
      positive: 1,
      neutral: 0,
      negative: 1,
      spam: 1,
      positive_pct: 50,
      neutral_pct: 0,
      negative_pct: 50,
    },
    top_posts: [
      {
        id: "p1",
        social_account_id: "a1",
        media_type: "IMAGE",
        caption: "New autumn cakes are here\nOrder today",
        media_url: null,
        thumbnail_url: "https://cdn.example/new.jpg",
        permalink: null,
        posted_at: "2026-09-22T06:30:00Z",
        comments: 3,
        stats: { total: 5, analysed: 4, positive: 2, neutral: 0, negative: 1, spam: 1 },
      },
    ],
    ...overrides,
  });
}

function setup({
  overview = busy(),
  ws = workspace,
  byRange,
  fail = false,
}: {
  overview?: Overview;
  ws?: typeof workspace;
  byRange?: (range: string, call: Call) => Overview;
  fail?: boolean;
} = {}) {
  return renderWithApi(<HomeScreen />, {
    ws,
    handlers: {
      "GET /v1/me": () => json({ id: "u1", email: "priya@example.com", name: "Priya Shah", workspaces: [ws] }),
      "GET /v1/w/:wid/overview": (call) => {
        if (fail) return problem(500, "internal");
        const range = call.url.searchParams.get("range") ?? "7d";
        return json(byRange ? byRange(range, call) : overview);
      },
    },
  });
}

function tile(label: string): HTMLElement {
  const found = screen.getAllByTestId("metric-tile").find((node) => node.textContent?.startsWith(label));
  if (!found) throw new Error(`No tile ${label}`);
  return found;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("Home (UX-SCR-01, FR-HOME-01)", () => {
  it("shows the four tiles with the API's numbers and the change from the week before", async () => {
    setup();
    await screen.findAllByTestId("metric-tile");

    const needsReply = tile("Needs reply");
    expect(needsReply).toHaveAttribute("href", "/w/maple/inbox?view=needs_reply");
    expect(within(needsReply).getByTestId("metric-value")).toHaveTextContent("2");
    expect(needsReply).toHaveTextContent("1 needs you");

    const today = tile("Messages today");
    expect(within(today).getByTestId("metric-value")).toHaveTextContent("2");
    expect(today).toHaveTextContent("9 in 7 days");
    expect(within(today).getByTestId("trend")).toHaveTextContent("down 25% from the previous 7 days");

    const ai = tile("Handled by AI, 7 days");
    expect(within(ai).getByTestId("metric-value")).toHaveTextContent("40%");
    expect(ai).toHaveTextContent("2 of 5 replied conversations");
    expect(within(ai).getByTestId("trend")).toHaveTextContent("+40 pts");

    const median = tile("Median first response, 7 days");
    expect(within(median).getByTestId("metric-value")).toHaveTextContent("7 min 45 s");
    expect(median).toHaveTextContent("Across 4 first replies");
    const faster = within(median).getByTestId("trend");
    expect(faster).toHaveTextContent("−87%");
    expect(faster).toHaveAttribute("data-tone", "good");
  });

  it("shows sentiment, the most commented posts, what customers asked, open questions and accounts to fix", async () => {
    setup();
    await screen.findAllByTestId("metric-tile");

    const messages = screen.getByTestId("sentiment-messages");
    expect(messages).toHaveTextContent("8 of 9 analysed");
    expect(within(messages).getByRole("img", { name: "Sentiment: 4 positive, 1 neutral, 2 negative" })).toBeInTheDocument();
    expect(within(messages).getByRole("list", { name: "Messages by sentiment" })).toHaveTextContent(
      "Positive 57%Neutral 14%Negative 29%Spam 1",
    );
    expect(screen.getByTestId("sentiment-comments")).toHaveTextContent("3 of 4 analysed");

    const [post] = screen.getAllByTestId("top-post");
    expect(post).toHaveAttribute("href", "/w/maple/comments/p1");
    expect(post).toHaveTextContent("New autumn cakes are here");
    expect(post).not.toHaveTextContent("Order today");
    expect(post).toHaveTextContent("3 comments");
    expect(within(post).getByRole("img", { name: "Sentiment: 2 positive, 0 neutral, 1 negative" })).toBeInTheDocument();

    expect(screen.getAllByTestId("top-intent").map((row) => row.textContent)).toEqual([
      "Pricing3 messages",
      "Complaint1 message",
      "Feedback1 message",
    ]);

    const gaps = screen.getByRole("link", { name: /^2 questions the AI couldn't answer/ });
    expect(gaps).toHaveAttribute("href", "/w/maple/knowledge");
    expect(screen.getByTestId("gap-topics")).toHaveTextContent("Most asked: Do you ship to Dubai? · Eggless options");

    const [account] = screen.getAllByTestId("account-attention");
    expect(account).toHaveTextContent("@maple.outlet needs reconnecting to keep receiving messages.");
    expect(screen.getByRole("link", { name: "Open Connections" })).toHaveAttribute("href", "/w/maple/settings/connections");
  });

  it("a new workspace: the checklist, and tiles with a dash and a hint instead of numbers", async () => {
    setup({ overview: empty() });
    expect(await screen.findByText("Get set up")).toBeInTheDocument();

    for (const label of ["Needs reply", "Messages today", "Handled by AI, 7 days", "Median first response, 7 days"]) {
      expect(within(tile(label)).getByTestId("metric-value")).toHaveTextContent("—");
    }
    expect(tile("Messages today")).toHaveTextContent("Counted once an account is connected.");
    expect(screen.queryByTestId("trend")).not.toBeInTheDocument();
    expect(screen.getByTestId("sentiment-messages")).toHaveTextContent("No messages in the last 7 days.");
    expect(screen.getByText("No comments on your posts in the last 7 days.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("sentiment-bar")).toHaveLength(0); // never a fake chart
    expect(screen.queryByRole("link", { name: /questions the AI couldn't answer/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Account health")).not.toBeInTheDocument();
  });

  it("connected but quiet: zeros where there is a count, a dash where there is nothing to divide", async () => {
    setup({ overview: empty({ checklist: { dismissed: true, completed: 1, steps: steps(true) } }) });
    await screen.findAllByTestId("metric-tile");
    expect(screen.queryByText("Get set up")).not.toBeInTheDocument();
    expect(within(tile("Needs reply")).getByTestId("metric-value")).toHaveTextContent("0");
    expect(within(tile("Messages today")).getByTestId("metric-value")).toHaveTextContent("0");
    expect(within(tile("Handled by AI, 7 days")).getByTestId("metric-value")).toHaveTextContent("—");
    expect(tile("Handled by AI, 7 days")).toHaveTextContent("No replies in the last 7 days yet.");
    expect(within(tile("Median first response, 7 days")).getByTestId("metric-value")).toHaveTextContent("—");
  });

  it("switches to 30 days, keeping the week on screen until the month arrives, and remembers it", async () => {
    const user = userEvent.setup();
    const ranges: string[] = [];
    setup({
      byRange: (range) => {
        ranges.push(range);
        return range === "30d"
          ? busy({
              range: "30d",
              messages_today: 2,
              current: { ...busy().current, since: "2026-09-01", messages_received: 11 },
              previous: { ...busy().previous, since: "2026-08-02", until: "2026-08-31" },
            })
          : busy();
      },
    });
    await screen.findAllByTestId("metric-tile");
    expect(screen.getByText(/Last 7 days/)).toHaveTextContent("Last 7 days · 24–30 Sep");

    await user.click(screen.getByRole("radio", { name: "30 days" }));

    await waitFor(() => expect(tile("Messages today")).toHaveTextContent("11 in 30 days"));
    expect(screen.getByText(/Last 30 days/)).toHaveTextContent("Last 30 days · 1–30 Sep");
    expect(tile("Handled by AI, 30 days")).toBeInTheDocument();
    expect(ranges).toEqual(["7d", "30d"]);
    expect(window.localStorage.getItem("socialhood:home-range:w1")).toBe("30d");
  });

  it("agents don't get the Knowledge link or the Connections button", async () => {
    setup({ ws: { ...workspace, role: "agent" } });
    await screen.findAllByTestId("metric-tile");
    expect(screen.queryByRole("link", { name: /questions the AI couldn't answer/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("account-attention")).toHaveTextContent("Ask an admin to fix it.");
    expect(screen.queryByRole("link", { name: "Open Connections" })).not.toBeInTheDocument();
  });

  it("shows an error with a retry when the overview can't load", async () => {
    setup({ fail: true });
    expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
