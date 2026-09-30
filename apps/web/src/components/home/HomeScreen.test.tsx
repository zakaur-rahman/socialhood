import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import type { ChecklistStep, Overview, PriorityConversation, SentimentSplit } from "@/lib/api/types";
import { dayKey } from "@/lib/tz";
import { json, knowledgeSource, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { HomeScreen } from "./HomeScreen";
import { addDays } from "./range";

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

/** Whole minutes before now, as Home's clock (useNow, to the minute) sees them. */
const minutesAgo = (minutes: number) =>
  new Date(Math.floor(Date.now() / 60_000) * 60_000 - minutes * 60_000).toISOString();

/** A new workspace: nothing connected, nothing counted. */
function empty(overrides: Partial<Overview> = {}): Overview {
  return {
    range: "7d",
    days: 7,
    timezone: "Asia/Kolkata",
    checklist: { dismissed: false, completed: 0, steps: steps(false) },
    needs_reply: 0,
    needs_you: 0,
    oldest_waiting_since: null,
    knowledge_gaps_open: 0,
    top_questions: [],
    latest_gap: null,
    accounts_needing_attention: [],
    accounts_connected: 0,
    platforms_connected: [],
    priority_queue: [],
    messages_today: 0,
    current: quietPeriod("2026-09-24", "2026-09-30"),
    previous: quietPeriod("2026-09-17", "2026-09-23"),
    top_intents: [],
    message_sentiment: nothing,
    comment_sentiment: nothing,
    top_posts: [],
    top_posts_engagement: null,
    ...overrides,
  };
}

function queueItem(overrides: Partial<PriorityConversation> = {}): PriorityConversation {
  return {
    id: "c1",
    platform: "instagram",
    contact: { id: "p1", display_name: "Priya Nair", username: "priya.styles", profile_picture_url: null },
    last_customer_message: "Do you ship to Dubai?",
    last_customer_message_at: minutesAgo(12),
    waiting_since: minutesAgo(12),
    needs_you: false,
    needs_human_reason: null,
    awaiting_reply: true,
    has_pending_suggestion: true,
    window_closes_at: null,
    lead_score: 80,
    priority: "high",
    ...overrides,
  };
}

/** The seed of the API's test (tests/integration/test_overview.py), as the API returns it. */
function busy(overrides: Partial<Overview> = {}): Overview {
  return empty({
    checklist: { dismissed: false, completed: 1, steps: steps(true) },
    needs_reply: 2,
    needs_you: 1,
    oldest_waiting_since: minutesAgo(90),
    knowledge_gaps_open: 2,
    top_questions: [
      { topic: "Do you ship to Dubai?", asked: 5 },
      { topic: "Eggless options", asked: 2 },
    ],
    latest_gap: {
      id: "g1",
      topic: "eggless options",
      question: "Any eggless cakes?",
      asked: 2,
      last_seen_at: minutesAgo(120),
      conversation_id: "c9",
      message_id: "m9",
    },
    accounts_needing_attention: [
      { id: "a2", platform: "instagram", username: "maple.outlet", status: "needs_reconnect" },
    ],
    accounts_connected: 2,
    platforms_connected: ["instagram", "whatsapp"],
    priority_queue: [
      queueItem({
        id: "c3",
        contact: { id: "p3", display_name: "Meera", username: null, profile_picture_url: null },
        needs_you: true,
        needs_human_reason: "complaint",
        has_pending_suggestion: false,
        last_customer_message: "This arrived broken.",
        last_customer_message_at: minutesAgo(180),
      }),
      queueItem(),
      queueItem({
        id: "c2",
        platform: "whatsapp",
        contact: { id: "p2", display_name: "Arjun K.", username: null, profile_picture_url: null },
        has_pending_suggestion: false,
        last_customer_message: "Can we schedule a demo tomorrow?",
        last_customer_message_at: minutesAgo(34),
      }),
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
        engagement_rate: null,
      },
    ],
    ...overrides,
  });
}

function setup({
  overview = busy(),
  ws = workspace,
  byQuery,
  fail = false,
  onPost,
}: {
  overview?: Overview;
  ws?: typeof workspace;
  byQuery?: (call: Call) => Overview | Promise<Overview>;
  fail?: boolean;
  onPost?: (body: unknown) => void;
} = {}) {
  return renderWithApi(<HomeScreen />, {
    ws,
    handlers: {
      "GET /v1/me": () => json({ id: "u1", email: "priya@example.com", name: "Priya Shah", workspaces: [ws] }),
      "GET /v1/w/:wid/overview": async (call) => {
        if (fail) return problem(500, "internal");
        return json(byQuery ? await byQuery(call) : overview);
      },
      "POST /v1/w/:wid/knowledge-sources": (call) => {
        onPost?.(call.body);
        return json(knowledgeSource({ question: "Any eggless cakes?" }), 201);
      },
    },
  });
}

function tile(label: string): HTMLElement {
  const found = screen.getAllByTestId("metric-tile").find((node) => node.textContent?.startsWith(label));
  if (!found) throw new Error(`No tile ${label}`);
  return found;
}

function overviewCalls(calls: Call[]): URLSearchParams[] {
  return calls.filter((call) => call.path === "/v1/w/w1/overview").map((call) => call.url.searchParams);
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

  it("labels Needs reply Attention after an hour's wait, and a median under 5 minutes Fast", async () => {
    const { unmount } = setup({
      overview: busy({ current: { ...busy().current, median_first_response_s: 54 } }),
    });
    await screen.findAllByTestId("metric-tile");
    expect(within(tile("Needs reply")).getByTestId("metric-badge")).toHaveTextContent("Attention");
    expect(within(tile("Median first response, 7 days")).getByTestId("metric-badge")).toHaveTextContent("Fast");
    unmount();

    // Waiting 30 minutes, a median of 7 min 45 s: neither.
    setup({ overview: busy({ oldest_waiting_since: minutesAgo(30) }) });
    await screen.findAllByTestId("metric-tile");
    expect(screen.queryAllByTestId("metric-badge")).toHaveLength(0);
  });

  it("the header: the greeting, the channels and the period in the workspace's days, and the channels pill", async () => {
    setup();
    expect(
      await screen.findByRole("heading", { level: 1, name: /^Good (morning|afternoon|evening), Priya$/ }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("home-subtitle")).toHaveTextContent(
      "Overview across Instagram & WhatsApp · Last 7 days · 24–30 Sep",
    );
    expect(screen.getByTestId("channels-pill")).toHaveTextContent("2 channels connected");
  });

  it("one channel, or none", async () => {
    const { unmount } = setup({ overview: busy({ accounts_connected: 1, platforms_connected: ["whatsapp"] }) });
    expect(await screen.findByTestId("channels-pill")).toHaveTextContent("1 channel connected");
    expect(screen.getByTestId("home-subtitle")).toHaveTextContent("Overview across WhatsApp ·");
    unmount();
    setup({ overview: empty() });
    expect(await screen.findByTestId("channels-pill")).toHaveTextContent("No channels connected");
    expect(screen.getByTestId("home-subtitle")).toHaveTextContent("No channels connected yet ·");
  });

  it("shows sentiment, the most commented posts, what customers asked and accounts to fix, and no invented figures", async () => {
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
    expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute("href", "/w/maple/comments");
    expect(screen.queryByTestId("engagement")).not.toBeInTheDocument(); // no snapshots, no figure

    expect(screen.getAllByTestId("top-intent").map((row) => row.textContent)).toEqual([
      "Pricing3 messages",
      "Complaint1 message",
      "Feedback1 message",
    ]);
    expect(screen.getByTestId("intents-total")).toHaveTextContent("5 messages in these topics");

    const [account] = screen.getAllByTestId("account-attention");
    expect(account).toHaveTextContent("@maple.outlet needs reconnecting to keep receiving messages.");
    expect(screen.getByRole("link", { name: "Open Connections" })).toHaveAttribute("href", "/w/maple/settings/connections");

    for (const fake of [/NLP Engine/i, /confidence/i, /accuracy/i, /Instagram Graph/i, /AI Classified/i]) {
      expect(screen.queryByText(fake)).not.toBeInTheDocument();
    }
  });

  it("shows the engagement rate only when the API measured one", async () => {
    setup({ overview: busy({ top_posts_engagement: { rate: 4.25, posts: 2 } }) });
    expect(await screen.findByTestId("engagement")).toHaveTextContent("Engagement rate 4.3%Average of 2 posts");
  });

  it("a new workspace: the checklist, and tiles with a dash and a hint instead of numbers", async () => {
    setup({ overview: empty() });
    expect(await screen.findByText("Get set up")).toBeInTheDocument();

    for (const label of ["Needs reply", "Messages today", "Handled by AI, 7 days", "Median first response, 7 days"]) {
      expect(within(tile(label)).getByTestId("metric-value")).toHaveTextContent("—");
    }
    expect(tile("Messages today")).toHaveTextContent("Counted once an account is connected.");
    expect(screen.queryByTestId("trend")).not.toBeInTheDocument();
    expect(screen.queryAllByTestId("metric-badge")).toHaveLength(0);
    expect(screen.getByTestId("sentiment-messages")).toHaveTextContent("No messages in the last 7 days.");
    expect(screen.getByText("No comments on your posts in the last 7 days.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("sentiment-bar")).toHaveLength(0); // never a fake chart
    expect(screen.queryByTestId("gap-banner")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Account health")).not.toBeInTheDocument();
    expect(screen.getByTestId("queue-empty")).toHaveTextContent("Nothing is waiting.");
    expect(screen.getByRole("link", { name: /Open Inbox/ })).toHaveTextContent("Open Inbox (0)");
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
    const { calls } = setup({
      byQuery: (call) =>
        call.url.searchParams.get("range") === "30d"
          ? busy({
              range: "30d",
              days: 30,
              current: { ...busy().current, since: "2026-09-01", messages_received: 11 },
              previous: { ...busy().previous, since: "2026-08-02", until: "2026-08-31" },
            })
          : busy(),
    });
    await screen.findAllByTestId("metric-tile");
    expect(screen.getByTestId("home-subtitle")).toHaveTextContent("Last 7 days · 24–30 Sep");

    await user.click(screen.getByRole("radio", { name: "30 days" }));

    await waitFor(() => expect(tile("Messages today")).toHaveTextContent("11 in 30 days"));
    expect(screen.getByTestId("home-subtitle")).toHaveTextContent("Last 30 days · 1–30 Sep");
    expect(tile("Handled by AI, 30 days")).toBeInTheDocument();
    expect(overviewCalls(calls).map((params) => params.get("range"))).toEqual(["7d", "30d"]);
    expect(window.localStorage.getItem("socialhood:home-range:w1")).toBe("30d");
  });

  it("Custom asks for two dates, checks them, and loads those days", async () => {
    const user = userEvent.setup();
    const today = dayKey(new Date(), "Asia/Kolkata");
    const from = addDays(today, -11);
    const { calls } = setup({
      byQuery: (call) =>
        call.url.searchParams.has("from")
          ? busy({
              range: "custom",
              days: 12,
              current: { ...busy().current, since: "2026-09-19", until: "2026-09-30", messages_received: 11 },
            })
          : busy(),
    });
    await screen.findAllByTestId("metric-tile");

    await user.click(screen.getByRole("radio", { name: "Custom" }));
    const picker = await screen.findByRole("form", { name: "Custom period" });
    const fromInput = within(picker).getByLabelText("From");
    const toInput = within(picker).getByLabelText("To");
    expect(toInput).toHaveAttribute("max", today);

    // A start after the end is refused before anything is sent.
    fireEvent.change(fromInput, { target: { value: addDays(today, 1) } });
    fireEvent.change(toInput, { target: { value: today } });
    await user.click(within(picker).getByRole("button", { name: "Apply" }));
    expect(within(picker).getByRole("alert")).toHaveTextContent("Pick a start date on or before the end date.");
    // More than 90 days too.
    fireEvent.change(fromInput, { target: { value: addDays(today, -90) } });
    await user.click(within(picker).getByRole("button", { name: "Apply" }));
    expect(within(picker).getByRole("alert")).toHaveTextContent("Pick at most 90 days.");
    expect(overviewCalls(calls)).toHaveLength(1);

    fireEvent.change(fromInput, { target: { value: from } });
    await user.click(within(picker).getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(tile("Messages today")).toHaveTextContent("11 in 12 days"));
    expect(screen.queryByRole("form", { name: "Custom period" })).not.toBeInTheDocument();
    const [, custom] = overviewCalls(calls);
    expect([custom.get("from"), custom.get("to"), custom.get("range")]).toEqual([from, today, null]);
    expect(screen.getByTestId("home-subtitle")).toHaveTextContent("12 days · 19–30 Sep");
    expect(tile("Handled by AI, 12 days")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Custom" })).toHaveAttribute("data-state", "on");
    expect(window.localStorage.getItem("socialhood:home-range:w1")).toBe(`custom:${from}:${today}`);
  });

  it("Refresh refetches the overview, spinning until it is back", async () => {
    const user = userEvent.setup();
    let release: () => void = () => {};
    let n = 0;
    const { calls } = setup({
      byQuery: () => {
        n += 1;
        if (n === 1) return busy();
        return new Promise<Overview>((resolve) => {
          release = () => resolve(busy({ messages_today: 3 }));
        });
      },
    });
    await screen.findAllByTestId("metric-tile");
    const button = screen.getByRole("button", { name: "Refresh" });

    await user.click(button);

    await waitFor(() => expect(overviewCalls(calls)).toHaveLength(2));
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toBeDisabled();
    release();
    await waitFor(() => expect(within(tile("Messages today")).getByTestId("metric-value")).toHaveTextContent("3"));
    expect(button).toHaveAttribute("aria-busy", "false");
  });

  it("the priority queue: who is waiting, since when, and what to do", async () => {
    setup();
    const rows = await screen.findAllByTestId("queue-row");
    expect(rows).toHaveLength(3);

    const [meera, priya, arjun] = rows;
    expect(meera).toHaveTextContent("Meera");
    expect(within(meera).getByTestId("queue-state")).toHaveTextContent("Needs you");
    expect(meera).toHaveTextContent("Handed to you: complaint");
    expect(meera).toHaveTextContent("3h ago");
    expect(within(meera).getByRole("link", { name: "Open chat: Meera" })).toHaveAttribute("href", "/w/maple/inbox/c3");

    expect(priya).toHaveTextContent("Priya Nair@priya.styles");
    expect(within(priya).getByTestId("queue-platform")).toHaveTextContent("Instagram");
    expect(priya).toHaveTextContent("12m ago");
    expect(priya).toHaveTextContent("“Do you ship to Dubai?”");
    expect(within(priya).getByTestId("queue-state")).toHaveTextContent("AI draft ready");
    expect(within(priya).getByRole("link", { name: "Review & Send: Priya Nair" })).toHaveAttribute(
      "href",
      "/w/maple/inbox/c1",
    );

    expect(within(arjun).getByTestId("queue-platform")).toHaveTextContent("WhatsApp");
    expect(within(arjun).getByTestId("queue-state")).toHaveTextContent("Needs reply");
    expect(within(arjun).getByRole("link", { name: "Open chat: Arjun K." })).toHaveAttribute("href", "/w/maple/inbox/c2");

    expect(screen.getByRole("link", { name: /Open Inbox/ })).toHaveAttribute("href", "/w/maple/inbox?view=needs_reply");
    expect(screen.getByRole("link", { name: /Open Inbox/ })).toHaveTextContent("Open Inbox (2)");
  });

  it("the gap banner: View thread opens the conversation; Train AI adds the question as an FAQ that answers the gap", async () => {
    const user = userEvent.setup();
    const posted: unknown[] = [];
    setup({ onPost: (body) => posted.push(body) });
    const banner = await screen.findByTestId("gap-banner");
    expect(within(banner).getByRole("heading")).toHaveTextContent("2 questions the AI couldn't answer");
    expect(within(banner).getByTestId("gap-topics")).toHaveTextContent("Most asked: Do you ship to Dubai? · Eggless options");
    expect(within(banner).getByTestId("gap-latest")).toHaveTextContent("Latest: “Any eggless cakes?”");
    expect(within(banner).getByRole("link", { name: "View thread" })).toHaveAttribute("href", "/w/maple/inbox/c9");

    await user.click(within(banner).getByRole("button", { name: "Train AI" }));
    const form = await screen.findByRole("form", { name: "Add an FAQ" });
    expect(within(form).getByLabelText("Question")).toHaveValue("Any eggless cakes?");
    await user.type(within(form).getByLabelText("Answer"), "Yes, every cake has an eggless option.");
    await user.click(within(form).getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(posted).toEqual([
        { type: "faq", question: "Any eggless cakes?", body: "Yes, every cake has an eggless option.", gap_id: "g1" },
      ]),
    );
  });

  it("a question from a comment has no thread to view", async () => {
    setup({
      overview: busy({
        latest_gap: {
          id: "g1",
          topic: "eggless options",
          question: "eggless options",
          asked: 2,
          last_seen_at: minutesAgo(5),
          conversation_id: null,
          message_id: null,
        },
      }),
    });
    const banner = await screen.findByTestId("gap-banner");
    expect(within(banner).queryByRole("link", { name: "View thread" })).not.toBeInTheDocument();
    expect(within(banner).getByRole("button", { name: "Train AI" })).toBeInTheDocument();
  });

  it("agents can view the thread but not train the AI or fix connections", async () => {
    setup({ ws: { ...workspace, role: "agent" } });
    const banner = await screen.findByTestId("gap-banner");
    expect(within(banner).getByRole("link", { name: "View thread" })).toBeInTheDocument();
    expect(within(banner).queryByRole("button", { name: "Train AI" })).not.toBeInTheDocument();
    expect(screen.getByTestId("account-attention")).toHaveTextContent("Ask an admin to fix it.");
    expect(screen.queryByRole("link", { name: "Open Connections" })).not.toBeInTheDocument();
  });

  it("shows an error with a retry when the overview can't load", async () => {
    setup({ fail: true });
    expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("keeps the last numbers when a refresh fails, and says so", async () => {
    const user = userEvent.setup();
    let n = 0;
    renderWithApi(<HomeScreen />, {
      handlers: {
        "GET /v1/me": () => json({ id: "u1", email: "priya@example.com", name: "Priya Shah", workspaces: [workspace] }),
        "GET /v1/w/:wid/overview": () => {
          n += 1;
          return n === 1 ? json(busy()) : problem(500, "internal");
        },
      },
    });
    await screen.findAllByTestId("metric-tile");
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByText(/Couldn't refresh/)).toBeInTheDocument();
    expect(within(tile("Needs reply")).getByTestId("metric-value")).toHaveTextContent("2");
  });
});
