import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import type { PostSummary, SocialAccount } from "@/lib/api/types";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import { account, json, post, postDetail, problem, renderWithApi, type Call } from "@/test/api";

import { CommentsPage } from "./CommentsPage";

beforeAll(() => {
  // jsdom lacks what Radix Select calls on open.
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const posts = [
  post({ id: "po1", posted_at: "2024-03-03T12:00:00Z" }),
  post({
    id: "po2",
    media_type: "reel",
    thumbnail_url: "https://scontent.cdninstagram.com/po2.jpg",
    caption: "Behind the scenes",
    posted_at: "2024-03-01T12:00:00Z",
    stats: { total: 8, analysed: 3, positive: 2, neutral: 1, negative: 0, spam: 0 },
  }),
];

function setup({
  items = posts,
  accounts = [account()],
  onList,
  failList = false,
  nextCursor = null,
}: {
  items?: PostSummary[];
  accounts?: SocialAccount[];
  onList?: (call: Call) => void;
  failList?: boolean;
  nextCursor?: string | null;
} = {}) {
  return renderWithApi(<CommentsPage />, {
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: accounts }),
      "GET /v1/w/:wid/posts": (call) => {
        onList?.(call);
        if (failList) return problem(500, "internal");
        const accountId = call.url.searchParams.get("account_id");
        const cursor = call.url.searchParams.get("cursor");
        if (cursor) return json({ items: [post({ id: "po3", posted_at: "2024-02-01T12:00:00Z" })], next_cursor: null });
        return json({
          items: accountId ? items.filter((p) => p.social_account_id === accountId) : items,
          next_cursor: nextCursor,
        });
      },
    },
  });
}

function card(id: string): HTMLElement {
  const found = screen.getAllByTestId("post-card").find((node) => node.dataset.postId === id);
  if (!found) throw new Error(`No card ${id}`);
  return found;
}

describe("Comments grid (FR-CMT-03, UX-SCR-05)", () => {
  it("shows each post: square thumbnail, date, comment count, 6 px sentiment bar and spam count", async () => {
    setup();
    await screen.findAllByTestId("post-card");

    const first = card("po1");
    expect(within(first).getByRole("link")).toHaveAttribute("href", "/w/maple/comments/po1");
    expect(within(first).getByText("3 Mar 2024")).toBeInTheDocument();
    expect(within(first).getByTestId("comment-count")).toHaveTextContent("12 comments");
    const bar = within(first).getByRole("img", { name: "Sentiment: 7 positive, 3 neutral, 1 negative" });
    expect(bar).toHaveClass("h-1.5"); // 6 px
    expect(bar.querySelectorAll("[data-sentiment]")).toHaveLength(3);
    expect(within(first).getByTestId("spam-count")).toHaveTextContent("1 spam");
    expect(first.querySelector(".aspect-square img")).toHaveAttribute("src", "https://scontent.cdninstagram.com/po1.jpg");

    const reel = card("po2");
    expect(reel.querySelector("img")).toHaveAttribute("src", "https://scontent.cdninstagram.com/po2.jpg");
    expect(within(reel).getByTestId("spam-count")).toHaveTextContent("No spam");
    // FR-CMT-02: still analysing
    expect(within(reel).getByText("Analysing 3 of 8")).toBeInTheDocument();
    // a zero count has no segment
    expect(within(reel).getByTestId("sentiment-bar").querySelectorAll("[data-sentiment]")).toHaveLength(2);
  });

  it("a new comment updates the card's counts live (post.updated, T6.4 done-when)", async () => {
    const { queryClient } = setup();
    await screen.findAllByTestId("post-card");
    expect(within(card("po1")).getByTestId("comment-count")).toHaveTextContent("12");

    act(() =>
      applyRealtimeEvent(queryClient, "w1", {
        id: "5-0",
        event: "post.updated",
        data: JSON.stringify({
          post: postDetail({
            id: "po1",
            posted_at: "2024-03-03T12:00:00Z",
            stats: { total: 13, analysed: 13, positive: 7, neutral: 3, negative: 2, spam: 1 },
          }),
        }),
      }),
    );

    await waitFor(() => expect(within(card("po1")).getByTestId("comment-count")).toHaveTextContent("13 comments"));
    expect(within(card("po1")).getByRole("img", { name: "Sentiment: 7 positive, 3 neutral, 2 negative" })).toBeInTheDocument();
  });

  it("filters by account when several Instagram accounts are connected", async () => {
    const user = userEvent.setup();
    const lists: (string | null)[] = [];
    setup({
      accounts: [account(), account({ id: "a2", username: "maple.studio" }), account({ id: "a3", platform: "whatsapp" })],
      items: [...posts, post({ id: "po7", social_account_id: "a2", posted_at: "2024-03-02T12:00:00Z" })],
      onList: (call) => lists.push(call.url.searchParams.get("account_id")),
    });
    await screen.findAllByTestId("post-card");
    expect(screen.getAllByTestId("post-card")).toHaveLength(3);

    await user.click(screen.getByRole("combobox", { name: "Account" }));
    // WhatsApp numbers have no posts, so they are not offered.
    expect(screen.queryByRole("option", { name: /whatsapp/i })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("option", { name: "@maple.studio" }));

    await waitFor(() => expect(screen.getAllByTestId("post-card")).toHaveLength(1));
    expect(card("po7")).toBeInTheDocument();
    expect(lists).toEqual([null, "a2"]);
  });

  it("hides the account filter with one account", async () => {
    setup();
    await screen.findAllByTestId("post-card");
    expect(screen.queryByRole("combobox", { name: "Account" })).not.toBeInTheDocument();
  });

  it("shows more posts on request", async () => {
    const user = userEvent.setup();
    setup({ nextCursor: "c2" });
    await screen.findAllByTestId("post-card");
    await user.click(screen.getByRole("button", { name: "Show more posts" }));
    await waitFor(() => expect(screen.getAllByTestId("post-card")).toHaveLength(3));
    expect(screen.queryByRole("button", { name: "Show more posts" })).not.toBeInTheDocument();
  });

  it("empty: without an Instagram account it offers to connect one (§4.7)", async () => {
    setup({ items: [], accounts: [] });
    expect(await screen.findByText("No posts yet")).toBeInTheDocument();
    expect(screen.getByText("Your Instagram posts and their comments appear here after you connect.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect Instagram" })).toHaveAttribute("href", "/w/maple/settings/connections");
  });

  it("empty: with an account connected it says posts appear once they sync", async () => {
    setup({ items: [] });
    expect(await screen.findByText("Your Instagram posts and their comments appear here once they sync.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Connect Instagram" })).not.toBeInTheDocument();
  });

  it("loads with skeleton cards and fails with Retry", async () => {
    setup({ failList: true });
    expect(screen.getByLabelText("Loading posts")).toBeInTheDocument();
    expect(await screen.findByText("This didn't load")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("at 375 px the grid has two columns, then 3 and 4 on wider screens", async () => {
    setup();
    const grid = await screen.findByTestId("posts-grid");
    expect(grid).toHaveClass("grid", "grid-cols-2", "md:grid-cols-3", "lg:grid-cols-4");
    // the thumbnail is square
    expect(card("po1").querySelector(".aspect-square")).not.toBeNull();
  });
});
