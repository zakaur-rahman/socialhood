import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { handOff, resetAgentHandoff, useAgentHandoff } from "@/lib/agent/handoff";
import type { CommentFilter, PostComment, PostDetail, WorkspaceSummary } from "@/lib/api/types";
import { matchesFilter, SECOND_PRIVATE_REPLY } from "@/lib/comments/format";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import {
  accepted,
  account,
  comment,
  comparison,
  json,
  noContent,
  performance,
  postDetail,
  problem,
  renderWithApi,
  workspace,
  type Call,
} from "@/test/api";
import { replyCard } from "@/test/agent";

import { NOTHING_TO_SUMMARIZE } from "./PostSummaryCard";
import { PostDetailPage } from "./PostDetailPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

const priya = comment({ id: "cm-priya", text: "What sizes do you have?", commented_at: "2026-09-28T11:00:00Z" });
const kabir = comment({
  id: "cm-kabir",
  contact_id: "p2",
  author_username: "kabir",
  text: "Took ages to arrive",
  commented_at: "2026-09-28T10:00:00Z",
  analysis: { sentiment: "negative", sentiment_score: -0.7, intent: "complaint", is_spam: false, topic: "delivery" },
});
const bot = comment({
  id: "cm-bot",
  contact_id: "p3",
  author_username: "free.followers",
  text: "Get 10k followers now",
  commented_at: "2026-09-28T09:00:00Z",
  analysis: { sentiment: "positive", sentiment_score: 0.1, intent: "spam", is_spam: true, topic: null },
});

type State = {
  detail: PostDetail | Response;
  comments: PostComment[];
  reply?: (call: Call, c: PostComment) => Response;
  privateReply?: (call: Call, c: PostComment) => Response;
  summary?: () => Response;
};

function setup(partial: Partial<State> = {}, ws: WorkspaceSummary = workspace) {
  const state: State = { detail: postDetail(), comments: [priya, kabir, bot], ...partial };
  const find = (id: string) => state.comments.find((c) => c.id === id)!;
  const update = (next: PostComment) => {
    state.comments = state.comments.map((c) => (c.id === next.id ? next : c));
    return next;
  };
  const view = renderWithApi(<PostDetailPage postId="po1" />, {
    ws,
    handlers: {
      "GET /v1/w/:wid/posts/:id": () => (state.detail instanceof Response ? state.detail : json(state.detail)),
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
      "GET /v1/w/:wid/posts/:id/comments": (call) => {
        const filter = (call.url.searchParams.get("filter") ?? "all") as CommentFilter;
        return json({ items: state.comments.filter((c) => matchesFilter(c, filter)), next_cursor: null });
      },
      "POST /v1/w/:wid/posts/:id/summary": () => state.summary?.() ?? accepted(),
      "POST /v1/w/:wid/comments/:id/reply": (call, p) => {
        if (state.reply) return state.reply(call, find(p.id));
        const text = (call.body as { text: string }).text;
        return json(update({ ...find(p.id), public_reply: { text, platform_id: "1799", replied_at: new Date().toISOString() } }));
      },
      "POST /v1/w/:wid/comments/:id/private-reply": (call, p) => {
        if (state.privateReply) return state.privateReply(call, find(p.id));
        return json(update({ ...find(p.id), private_reply: { message_id: "m9", conversation_id: "c9" } }), 202);
      },
      "POST /v1/w/:wid/comments/:id/hide": (_, p) => json(update({ ...find(p.id), hidden: true })),
      "POST /v1/w/:wid/comments/:id/unhide": (_, p) => json(update({ ...find(p.id), hidden: false })),
      "DELETE /v1/w/:wid/comments/:id": (_, p) => {
        state.comments = state.comments.filter((c) => c.id !== p.id);
        return noContent();
      },
      "GET /v1/w/:wid/analytics/posts/:id/performance": () => json(performance()),
      "GET /v1/w/:wid/analytics/posts/:id/compare": () => json(comparison()),
    },
  });
  const posted = (suffix: string) => view.calls.filter((c) => c.method === "POST" && c.path.endsWith(suffix));
  return { ...view, state, posted };
}

function row(name: string): HTMLElement {
  return screen.getByRole("listitem", { name: `Comment by ${name}` });
}

function send(queryClient: Parameters<typeof applyRealtimeEvent>[0], event: string, data: unknown) {
  act(() => applyRealtimeEvent(queryClient, "w1", { id: "9-0", event, data: JSON.stringify(data) }));
}

describe("Post detail: the post, summary and topics (FR-CMT-04, UX-SCR-05)", () => {
  it("shows the post, caption, counts and sentiment split", async () => {
    setup();
    const panel = await screen.findByRole("region", { name: "Post" });
    expect(within(panel).getByText("New linen dresses are here")).toBeInTheDocument();
    expect(within(panel).getByText("Likes").nextElementSibling).toHaveTextContent("1,204");
    expect(within(panel).getByText("Comments").nextElementSibling).toHaveTextContent("12");
    expect(within(panel).getByRole("img", { name: "Sentiment: 7 positive, 3 neutral, 1 negative" })).toBeInTheDocument();
    expect(within(panel).getByRole("list", { name: "Comment counts" })).toHaveTextContent("Spam 1");
    expect(within(panel).getByRole("link", { name: "Open in Instagram" })).toHaveAttribute("href", "https://www.instagram.com/p/po1/");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/^Photo from /);
    expect(screen.getByRole("link", { name: "Comments" })).toHaveAttribute("href", "/w/maple/comments");
  });

  it("shows the summary and the topics with counts and a small sentiment bar", async () => {
    setup();
    const summary = await screen.findByRole("region", { name: "Summary" });
    expect(summary).toHaveTextContent("People love the colours and ask about sizes.");
    const topics = within(screen.getByRole("region", { name: "Topics" })).getAllByRole("listitem");
    expect(topics.map((t) => t.textContent)).toEqual(["sizes5 comments", "shipping to uae3 comments"]);
    const bar = within(topics[1]).getByRole("img", { name: "Sentiment: 1 positive, 1 neutral, 1 negative" });
    expect(bar).toHaveClass("h-1");
  });

  it("Refresh asks for a summary (202) and waits for the post.updated that brings it", async () => {
    const user = userEvent.setup();
    const { posted, queryClient } = setup();
    const summary = await screen.findByRole("region", { name: "Summary" });
    await user.click(within(summary).getByRole("button", { name: "Refresh" }));

    expect(posted("/posts/po1/summary")).toHaveLength(1);
    expect(await within(summary).findByRole("status")).toHaveTextContent("Updating the summary…");
    expect(within(summary).getByRole("button", { name: "Refresh" })).toBeDisabled();

    // an unrelated update (new counts, same summary) keeps waiting
    send(queryClient, "post.updated", { post: postDetail({ stats: { ...postDetail().stats, total: 13 } }) });
    expect(within(summary).getByRole("status")).toBeInTheDocument();

    send(queryClient, "post.updated", {
      post: postDetail({
        summary: "Most people ask about sizes; two complain about delivery times.",
        summary_updated_at: new Date().toISOString(),
      }),
    });
    expect(await within(summary).findByText("Most people ask about sizes; two complain about delivery times.")).toBeInTheDocument();
    expect(within(summary).queryByRole("status")).not.toBeInTheDocument();
    expect(within(summary).getByText("Updated just now")).toBeInTheDocument();
  });

  it("Refresh with nothing analysed yet (409) says so", async () => {
    const user = userEvent.setup();
    setup({ summary: () => problem(409, "conflict", "No analysed comments") });
    const summary = await screen.findByRole("region", { name: "Summary" });
    await user.click(within(summary).getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(NOTHING_TO_SUMMARIZE));
    expect(within(summary).queryByRole("status")).not.toBeInTheDocument();
  });

  it("before the first summary and topics", async () => {
    setup({
      detail: postDetail({
        summary: null,
        summary_updated_at: null,
        topics: [],
        stats: { total: 4, analysed: 0, positive: 0, neutral: 0, negative: 0, spam: 0 },
      }),
    });
    const summary = await screen.findByRole("region", { name: "Summary" });
    expect(summary).toHaveTextContent("No summary yet. It appears once comments are analysed.");
    expect(within(summary).getByRole("button", { name: "Summarize" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Topics" })).toHaveTextContent("Topics appear once comments are analysed.");
    expect(screen.getByRole("img", { name: "No analysed comments yet" })).toBeInTheDocument();
  });

  it("FR-CMT-02: shows analysis progress while comments are analysed, until they all are", async () => {
    const { queryClient } = setup({
      detail: postDetail({ stats: { total: 58_000, analysed: 12_400, positive: 9000, neutral: 3000, negative: 300, spam: 100 } }),
    });
    const progress = await screen.findByTestId("analysis-progress");
    expect(within(progress).getByRole("status")).toHaveTextContent("Analysing 12,400 of 58,000 comments");
    const bar = within(progress).getByRole("progressbar", { name: "Comments analysed" });
    expect(bar).toHaveAttribute("aria-valuenow", "12400");
    expect(bar).toHaveAttribute("aria-valuemax", "58000");

    send(queryClient, "post.updated", {
      post: postDetail({ stats: { total: 58_000, analysed: 58_000, positive: 40_000, neutral: 15_000, negative: 2_500, spam: 500 } }),
    });
    await waitFor(() => expect(screen.queryByTestId("analysis-progress")).not.toBeInTheDocument());
  });

  it("says when AI analysis is off for the account instead of showing progress", async () => {
    renderWithApi(<PostDetailPage postId="po1" />, {
      handlers: {
        "GET /v1/w/:wid/posts/:id": () => json(postDetail({ stats: { ...postDetail().stats, analysed: 2 } })),
        "GET /v1/w/:wid/social-accounts": () => json({ items: [account({ ai_analysis_enabled: false })] }),
        "GET /v1/w/:wid/posts/:id/comments": () => json({ items: [], next_cursor: null }),
        "GET /v1/w/:wid/analytics/posts/:id/performance": () => json(performance()),
        "GET /v1/w/:wid/analytics/posts/:id/compare": () => json(comparison()),
      },
    });
    expect(await screen.findByText(/AI analysis is off for @maple.bakery/)).toBeInTheDocument();
    expect(screen.queryByTestId("analysis-progress")).not.toBeInTheDocument();
  });

  it("an unknown post says it was not found", async () => {
    setup({ detail: problem(404, "not_found") });
    expect(await screen.findByText("Post not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Comments" })).toHaveAttribute("href", "/w/maple/comments");
  });

  it("shows the post's performance beside the comments (FR-ANL-02)", async () => {
    setup();
    const card = await screen.findByRole("region", { name: "Performance" });
    expect(await within(card).findByTestId("figures-age")).toHaveTextContent("Figures at 24 h after posting");
    expect(await within(card).findByTestId("baseline")).toHaveTextContent("Compared with 8 earlier feed posts");
  });
});

describe("Comment list and filter chips (UX-SCR-05)", () => {
  it("rows show avatar, @username, time, text, sentiment dot and intent chip", async () => {
    setup();
    await screen.findByRole("list", { name: "Comments" });
    const first = row("@priya.styles");
    expect(within(first).getByTestId("contact-avatar")).toBeInTheDocument();
    expect(within(first).getByText("What sizes do you have?")).toBeInTheDocument();
    expect(within(first).getByRole("img", { name: "Positive sentiment" })).toHaveClass("bg-success");
    expect(within(first).getByText("Product question")).toBeInTheDocument();
    const time = first.querySelector("time");
    expect(time).toHaveAttribute("datetime", "2026-09-28T11:00:00Z");
    expect(time?.textContent).not.toBe("");

    expect(within(row("@kabir")).getByRole("img", { name: "Negative sentiment" })).toHaveClass("bg-danger");
    expect(within(row("@kabir")).getByText("Complaint")).toBeInTheDocument();
    // spam shows a Spam chip instead of a sentiment
    expect(within(row("@free.followers")).getByText("Spam")).toBeInTheDocument();
    expect(within(row("@free.followers")).queryByRole("img", { name: /sentiment/ })).not.toBeInTheDocument();
  });

  it("each chip asks the API for its filter", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findByRole("list", { name: "Comments" });
    const chips = screen.getByRole("radiogroup", { name: "Filter comments" });
    expect(within(chips).getAllByRole("radio").map((r) => r.textContent)).toEqual([
      "All",
      "Positive",
      "Neutral",
      "Negative",
      "Questions",
      "Buying signals",
      "Spam",
      "Hidden",
    ]);
    expect(within(chips).getByRole("radio", { name: "All" })).toHaveAttribute("aria-checked", "true");

    await user.click(within(chips).getByRole("radio", { name: "Negative" }));
    await waitFor(() => expect(screen.getAllByTestId("comment-row")).toHaveLength(1));
    expect(row("@kabir")).toBeInTheDocument();

    await user.click(within(chips).getByRole("radio", { name: "Spam" }));
    await waitFor(() => expect(row("@free.followers")).toBeInTheDocument());
    expect(screen.getAllByTestId("comment-row")).toHaveLength(1);

    await user.click(within(chips).getByRole("radio", { name: "Buying signals" }));
    expect(await screen.findByText("No buying signals")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show all" }));
    await waitFor(() => expect(screen.getAllByTestId("comment-row")).toHaveLength(3));

    const asked = calls.filter((c) => c.path.endsWith("/posts/po1/comments")).map((c) => c.url.searchParams.get("filter"));
    expect(asked).toEqual(["all", "negative", "spam", "buying"]);
  });

  it("new comments and changes arrive live (comment.created, comment.updated)", async () => {
    const { queryClient } = setup();
    await screen.findByRole("list", { name: "Comments" });

    const fresh = comment({
      id: "cm-new",
      contact_id: "p4",
      author_username: "aisha",
      text: "Is the blue one back?",
      commented_at: new Date().toISOString(),
      analysis_status: "pending",
      analysis: null,
    });
    send(queryClient, "comment.created", { comment: fresh });
    await waitFor(() => expect(screen.getAllByTestId("comment-row")[0]).toHaveAttribute("data-comment-id", "cm-new"));
    expect(within(row("@aisha")).queryByRole("img", { name: /sentiment/ })).not.toBeInTheDocument();

    send(queryClient, "comment.updated", {
      comment: {
        ...fresh,
        analysis_status: "done",
        analysis: { sentiment: "neutral", sentiment_score: 0, intent: "product_inquiry", is_spam: false, topic: "colours" },
      },
    });
    await waitFor(() => expect(within(row("@aisha")).getByRole("img", { name: "Neutral sentiment" })).toBeInTheDocument());

    send(queryClient, "comment.updated", { comment: { ...kabir, deleted_at: new Date().toISOString() } });
    await waitFor(() => expect(screen.queryByRole("listitem", { name: "Comment by @kabir" })).not.toBeInTheDocument());
  });
});

describe("Comment actions (FR-CMT-04)", () => {
  it("Reply opens an inline composer and posts a public reply with an Idempotency-Key", async () => {
    const user = userEvent.setup();
    const { posted } = setup();
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@priya.styles")).getByRole("button", { name: "Reply to @priya.styles" }));

    const box = within(row("@priya.styles")).getByRole("textbox", { name: "Public reply to @priya.styles" });
    expect(box).toHaveFocus();
    await user.type(box, "XS to XL, all in stock{Enter}");

    await waitFor(() => expect(posted("/comments/cm-priya/reply")).toHaveLength(1));
    const call = posted("/comments/cm-priya/reply")[0];
    expect(call.body).toEqual({ text: "XS to XL, all in stock" });
    expect(call.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    await waitFor(() => expect(within(row("@priya.styles")).getByTestId("public-reply")).toHaveTextContent("XS to XL, all in stock"));
    expect(within(row("@priya.styles")).queryByRole("textbox")).not.toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("Reply posted");
  });

  it("a failed reply keeps the text, says why, and retries with the same Idempotency-Key", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    const { posted } = setup({
      reply: (call, c) => {
        attempts += 1;
        return attempts === 1
          ? problem(503, "platform_unavailable")
          : json({ ...c, public_reply: { text: "Thanks!", platform_id: "1", replied_at: new Date().toISOString() } });
      },
    });
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@kabir")).getByRole("button", { name: "Reply to @kabir" }));
    await user.type(within(row("@kabir")).getByRole("textbox"), "Thanks!");
    await user.click(within(row("@kabir")).getByRole("button", { name: "Send reply" }));

    expect(await within(row("@kabir")).findByRole("alert")).toHaveTextContent("Instagram didn't respond.");
    expect(within(row("@kabir")).getByRole("textbox")).toHaveValue("Thanks!");
    await user.click(within(row("@kabir")).getByRole("button", { name: "Send reply" }));
    await waitFor(() => expect(posted("/comments/cm-kabir/reply")).toHaveLength(2));
    const [first, second] = posted("/comments/cm-kabir/reply");
    expect(second.headers.get("Idempotency-Key")).toBe(first.headers.get("Idempotency-Key"));
    await waitFor(() => expect(within(row("@kabir")).queryByRole("textbox")).not.toBeInTheDocument());
  });

  it("Esc closes the composer without sending", async () => {
    const user = userEvent.setup();
    const { posted } = setup();
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@kabir")).getByRole("button", { name: "Reply to @kabir" }));
    await user.type(within(row("@kabir")).getByRole("textbox"), "Sorry{Escape}");
    expect(within(row("@kabir")).queryByRole("textbox")).not.toBeInTheDocument();
    expect(posted("/reply")).toHaveLength(0);
  });

  it("DM sends the one private reply (202); the row then links to the conversation", async () => {
    const user = userEvent.setup();
    const { posted } = setup();
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@priya.styles")).getByRole("button", { name: "DM @priya.styles" }));
    const composer = within(row("@priya.styles")).getByTestId("composer-dm");
    expect(composer).toHaveTextContent("Instagram allows one private reply per comment, within 7 days of it.");
    await user.type(within(composer).getByRole("textbox", { name: "Private reply to @priya.styles" }), "Here's the size chart");
    expect(within(composer).getByText("21 / 1,000 bytes")).toBeInTheDocument();
    await user.click(within(composer).getByRole("button", { name: "Send DM" }));

    await waitFor(() => expect(posted("/comments/cm-priya/private-reply")).toHaveLength(1));
    const call = posted("/comments/cm-priya/private-reply")[0];
    expect(call.body).toEqual({ text: "Here's the size chart" });
    expect(call.headers.get("Idempotency-Key")).toBeTruthy();
    const link = await within(row("@priya.styles")).findByRole("link", { name: "View DM to @priya.styles" });
    expect(link).toHaveAttribute("href", "/w/maple/inbox/c9");
    expect(within(row("@priya.styles")).queryByRole("button", { name: "DM @priya.styles" })).not.toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("DM on its way to @priya.styles");
  });

  it("a second private reply is refused with a clear message (409)", async () => {
    const user = userEvent.setup();
    setup({ privateReply: () => problem(409, "conflict", "This comment already has a private reply.") });
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@kabir")).getByRole("button", { name: "DM @kabir" }));
    await user.type(within(row("@kabir")).getByRole("textbox"), "Sorry about that{Enter}");
    expect(await within(row("@kabir")).findByRole("alert")).toHaveTextContent(SECOND_PRIVATE_REPLY);
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("a DM over 1,000 bytes cannot be sent", async () => {
    const user = userEvent.setup();
    setup();
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@kabir")).getByRole("button", { name: "DM @kabir" }));
    const box = within(row("@kabir")).getByRole("textbox");
    await user.click(box);
    await user.paste("😍".repeat(251)); // 1,004 bytes
    expect(within(row("@kabir")).getByText("1,004 / 1,000 bytes")).toHaveClass("text-danger-fg");
    expect(within(row("@kabir")).getByRole("button", { name: "Send DM" })).toBeDisabled();
  });

  it("Hide and Unhide change the comment on Instagram and the row follows", async () => {
    const user = userEvent.setup();
    const { posted } = setup();
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@kabir")).getByRole("button", { name: "Hide @kabir's comment" }));
    await waitFor(() => expect(within(row("@kabir")).getByText("Hidden")).toBeInTheDocument());
    expect(posted("/comments/cm-kabir/hide")).toHaveLength(1);
    expect(toast.success).toHaveBeenCalledWith("Comment hidden. Only its author can still see it.");

    await user.click(within(row("@kabir")).getByRole("button", { name: "Unhide @kabir's comment" }));
    await waitFor(() => expect(within(row("@kabir")).queryByText("Hidden")).not.toBeInTheDocument());
    expect(posted("/comments/cm-kabir/unhide")).toHaveLength(1);
  });

  it("Delete asks to confirm, then deletes on Instagram and drops the row (admins)", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findByRole("list", { name: "Comments" });
    const deletes = () => calls.filter((c) => c.method === "DELETE");

    const trigger = within(row("@free.followers")).getByRole("button", { name: "Delete @free.followers's comment" });
    // The row's trigger is the quiet destructive look; the confirming button is the solid one (DESIGN_SYSTEM §8.2).
    expect(trigger).toHaveAttribute("data-variant", "destructive-ghost");
    await user.click(trigger);
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this comment?" });
    expect(dialog).toHaveTextContent("It's deleted on Instagram for everyone, @free.followers included.");
    expect(within(dialog).getByRole("button", { name: "Delete comment" })).toHaveAttribute("data-variant", "destructive");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(deletes()).toHaveLength(0);

    await user.click(within(row("@free.followers")).getByRole("button", { name: "Delete @free.followers's comment" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete comment" }));
    await waitFor(() => expect(deletes()).toHaveLength(1));
    expect(deletes()[0].path).toBe("/v1/w/w1/comments/cm-bot");
    await waitFor(() => expect(screen.queryByRole("listitem", { name: "Comment by @free.followers" })).not.toBeInTheDocument());
    expect(toast.success).toHaveBeenCalledWith("Comment deleted");
  });

  it("agents can reply, DM and hide, but not delete", async () => {
    setup({}, { ...workspace, role: "agent" });
    await screen.findByRole("list", { name: "Comments" });
    const actions = within(row("@kabir"));
    expect(actions.getByRole("button", { name: "Reply to @kabir" })).toBeInTheDocument();
    expect(actions.getByRole("button", { name: "DM @kabir" })).toBeInTheDocument();
    expect(actions.getByRole("button", { name: "Hide @kabir's comment" })).toBeInTheDocument();
    expect(actions.queryByRole("button", { name: /Delete/ })).not.toBeInTheDocument();
  });

  it("a platform refusal on hide is shown as the inbox words it", async () => {
    const user = userEvent.setup();
    renderWithApi(<PostDetailPage postId="po1" />, {
      handlers: {
        "GET /v1/w/:wid/posts/:id": () => json(postDetail()),
        "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
        "GET /v1/w/:wid/posts/:id/comments": () => json({ items: [kabir], next_cursor: null }),
        "POST /v1/w/:wid/comments/:id/hide": () => problem(409, "account_needs_reconnect"),
        "GET /v1/w/:wid/analytics/posts/:id/performance": () => json(performance()),
        "GET /v1/w/:wid/analytics/posts/:id/compare": () => json(comparison()),
      },
    });
    await screen.findByRole("list", { name: "Comments" });
    await user.click(within(row("@kabir")).getByRole("button", { name: "Hide @kabir's comment" }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("@maple.bakery needs reconnecting before you can send from it."),
    );
  });
});

describe("A reply prepared by Ask Social Hood (FR-AGT-03)", () => {
  beforeEach(() => resetAgentHandoff());

  it("opens that comment's reply box with the text; the member edits and sends it", async () => {
    const user = userEvent.setup();
    handOff(replyCard());
    const { posted } = setup();
    const box = await within(await screen.findByRole("listitem", { name: "Comment by @kabir" })).findByRole("textbox", {
      name: "Public reply to @kabir",
    });
    expect(box).toHaveValue("Sorry about the wait! It ships today.");
    expect(box).toHaveFocus();
    // Nothing was sent by the hand-off.
    expect(posted("/reply")).toHaveLength(0);
    expect(within(row("@priya.styles")).queryByRole("textbox")).toBeNull();
    await user.type(box, " Thanks for waiting.{Enter}");
    await waitFor(() => expect(posted("/comments/cm-kabir/reply")).toHaveLength(1));
    expect(posted("/comments/cm-kabir/reply")[0].body).toEqual({
      text: "Sorry about the wait! It ships today. Thanks for waiting.",
    });
    expect(useAgentHandoff.getState().commentReply).toBeNull();
  });

  it("a private reply opens the DM box", async () => {
    handOff(replyCard({ prefill: { ...replyCard().prefill, private: true } }));
    setup();
    const composer = await within(await screen.findByRole("listitem", { name: "Comment by @kabir" })).findByTestId("composer-dm");
    expect(within(composer).getByRole("textbox", { name: "Private reply to @kabir" })).toHaveValue(
      "Sorry about the wait! It ships today.",
    );
  });

  it("says so when the comment isn't there, keeping the prepared text", async () => {
    handOff(replyCard({ prefill: { ...replyCard().prefill, comment_id: "cm-gone" } }));
    setup();
    const notice = await screen.findByTestId("prepared-missing");
    expect(notice).toHaveTextContent("isn't among this post's latest comments");
    expect(notice).toHaveTextContent("Sorry about the wait! It ships today.");
  });

  it("a reply for another post is left for that post", async () => {
    handOff(replyCard({ prefill: { ...replyCard().prefill, post_id: "po9" } }));
    setup();
    await screen.findByRole("list", { name: "Comments" });
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(useAgentHandoff.getState().commentReply).not.toBeNull();
  });
});

describe("Layout at 375 px (UX-A11Y-05)", () => {
  it("stacks into one column on phones, with a 340 px left column from 1024 px", async () => {
    setup();
    const layout = await screen.findByTestId("post-detail");
    expect(layout).toHaveClass("grid", "lg:grid-cols-[340px_minmax(0,1fr)]");
    expect(layout.className).not.toMatch(/(^|\s)grid-cols-/);
    // the thumbnail is small beside the caption on phones and full width in the column on desktop
    const thumb = screen.getByRole("region", { name: "Post" }).querySelector(".aspect-square");
    expect(thumb).toHaveClass("w-24", "lg:w-full");
  });

  it("chips wrap and every action is a 40 px target on touch", async () => {
    setup();
    await screen.findByRole("list", { name: "Comments" });
    expect(screen.getByTestId("comment-filters")).toHaveClass("flex-wrap");
    // UI-038: the 40 px comes from the primitives on coarse pointers (DESIGN_SYSTEM §8.4), not from a
    // `min-h-10 md:min-h-*` patch keyed to the viewport: the segment's 32 px and the `sm` Button's 28 px
    // stay with a mouse, at any width.
    for (const chip of within(screen.getByTestId("comment-filters")).getAllByRole("radio")) {
      expect(chip).toHaveClass("min-h-8", "pointer-coarse:min-h-10");
      expect(chip.className).not.toMatch(/(^|\s)(min-h-10|md:min-h-8)(\s|$)/);
    }
    for (const button of within(row("@kabir")).getAllByRole("button")) {
      expect(button).toHaveClass("h-7", "pointer-coarse:min-h-10");
      expect(button.className).not.toMatch(/(^|\s)(min-h-10|md:min-h-7)(\s|$)/);
    }
  });
});
