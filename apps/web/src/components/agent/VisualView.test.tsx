import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Visual } from "@/lib/api/types";
import { renderWithApi } from "@/test/api";
import { comparisonVisual, metricDelta, rankedVisual, sentimentVisual } from "@/test/agent";

import { VisualView } from "./VisualView";

const sentry = vi.hoisted(() => ({ captureException: vi.fn() }));
vi.mock("@sentry/nextjs", () => sentry);

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/w/maple/ask",
}));

function show(visual: Visual, onNavigate?: () => void) {
  return renderWithApi(<VisualView visual={visual} slug="maple" onNavigate={onNavigate} />);
}

beforeEach(() => {
  sentry.captureException.mockReset();
});

describe("MetricComparison (GR-38): a card per metric with the API's figures", () => {
  it("shows each figure, the previous one and the change with its tone", () => {
    show(comparisonVisual());
    const section = screen.getByRole("region", { name: "@maple.bakery: 1-22 Oct 2026 against 1-22 Sep 2026" });
    expect(within(section).getByText("Compared over the same 22 days of each period.")).toBeInTheDocument();

    const tiles = within(section).getAllByTestId("metric-tile");
    expect(tiles).toHaveLength(3);
    const reach = tiles[0];
    expect(within(reach).getByText("Reach")).toBeInTheDocument();
    expect(within(reach).getByTestId("metric-value")).toHaveTextContent("11,800");
    expect(within(reach).getByText("1-22 Sep 2026: 10,000")).toBeInTheDocument();
    expect(within(reach).getByTestId("trend")).toHaveAttribute("data-tone", "good");
    expect(within(reach).getByTestId("trend")).toHaveTextContent("+18%");
    // The words a screen reader gets, beside the arrow and the sign.
    expect(within(reach).getByText("up 18% from 1-22 Sep 2026")).toHaveClass("sr-only");

    // Fewer comments is bad news; more unfollows too (the API's tone, not the arrow).
    expect(within(tiles[1]).getByTestId("trend")).toHaveAttribute("data-tone", "bad");
    expect(within(tiles[1]).getByTestId("trend")).toHaveTextContent("−9%");
    expect(within(tiles[2]).getByTestId("trend")).toHaveAttribute("data-tone", "bad");
    expect(within(tiles[2]).getByTestId("trend")).toHaveTextContent("+50%");
  });

  it("a figure that isn't available shows a dash and why, never a zero", () => {
    const reason = "Insights aren't granted for @maple.bakery, so this isn't available.";
    show(
      comparisonVisual({
        metrics: [metricDelta({ current: null, previous: null, change_pct: null, direction: null, tone: "neutral", unavailable: reason })],
      }),
    );
    const tile = screen.getByTestId("metric-tile");
    expect(within(tile).getByTestId("metric-value")).toHaveTextContent("—");
    expect(within(tile).getByText(reason)).toBeInTheDocument();
    expect(within(tile).queryByTestId("trend")).toBeNull();
    expect(tile).not.toHaveTextContent("0");
  });

  it("says how many days a figure with gaps has", () => {
    show(comparisonVisual({ metrics: [metricDelta({ current_coverage: "21 of 22 days" })] }));
    expect(screen.getByText("This period: 21 of 22 days")).toBeInTheDocument();
  });

  it("periods of different length show the totals without a change, and say so", () => {
    show(
      comparisonVisual({
        comparable: false,
        note: "The periods are 30 and 7 days long, so no change is worked out.",
        metrics: [metricDelta({ current: 300, previous: 70, change_pct: null, direction: null, tone: "neutral" })],
      }),
    );
    expect(screen.getByText(/so no change is worked out/)).toBeInTheDocument();
    expect(screen.getByTestId("metric-value")).toHaveTextContent("300");
    expect(screen.queryByTestId("trend")).toBeNull();
  });

  it("explains the daily totals once, and has an empty state", () => {
    const { unmount } = show(comparisonVisual());
    expect(screen.getByText(/add up each day's figure\. Followers is the latest count|counts twice/)).toBeInTheDocument();
    unmount();
    show(comparisonVisual({ metrics: [] }));
    expect(screen.getByText("No figures to compare.")).toBeInTheDocument();
  });

  it("is a list of cards that stack in a narrow column (container query classes)", () => {
    show(comparisonVisual());
    const list = screen.getByRole("list");
    expect(list.className).toContain("grid-cols-1");
    expect(list.className).toContain("@xs:grid-cols-2");
    expect(screen.getByTestId("visual-metric-comparison").className).toContain("@container");
  });
});

describe("RankedPosts (GR-38)", () => {
  it("lists the posts best first with the figure, each linking to its post", async () => {
    const onNavigate = vi.fn();
    show(rankedVisual(), onNavigate);
    const section = screen.getByRole("region", { name: "Top posts by reach" });
    expect(within(section).getByText("Posts published 1-22 Oct 2026 · Latest figures · 7 posts compared")).toBeInTheDocument();
    const rows = within(section).getAllByTestId("ranked-post");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("1");
    expect(rows[0]).toHaveTextContent("Reel of 12 Oct");
    expect(rows[0]).toHaveTextContent("Summer sale");
    expect(rows[0]).toHaveTextContent("4,120");
    expect(rows[1]).toHaveTextContent("2,900");
    const link = within(rows[0]).getByRole("link");
    expect(link).toHaveAttribute("href", "/w/maple/comments/po1");
    link.addEventListener("click", (event) => event.preventDefault());
    await userEvent.click(link);
    expect(onNavigate).toHaveBeenCalled();
    expect(within(section).getByRole("columnheader", { name: "Reach" })).toBeInTheDocument();
    expect(within(section).getByRole("table")).toBeInTheDocument();
  });

  it("shows percentages for the engagement rate and a placeholder without a picture", () => {
    const { container } = show(
      rankedVisual({
        metric_key: "engagement_rate",
        metric_label: "Engagement rate",
        format: "percent",
        items: [{ post_id: "po2", label: "Post of 3 Oct", format: "feed", caption: null, thumbnail_url: null, value: 6.14 }],
      }),
    );
    expect(screen.getByTestId("ranked-post")).toHaveTextContent("6.1%");
    expect(container.querySelector("img")).toBeNull();
  });

  it("draws a customer's caption as text, and refuses a picture that isn't https", () => {
    const caption = "<img src=x onerror=alert(1)> Summer sale";
    const { container } = show(
      rankedVisual({
        items: [
          { post_id: "po1", label: "Reel of 12 Oct", format: "reel", caption, thumbnail_url: "javascript:alert(1)", value: 5 },
          { post_id: "po2", label: "Post of 3 Oct", format: "feed", caption: "‮evil", thumbnail_url: "http://cdn.example/a.jpg", value: 4 },
        ],
      }),
    );
    expect(screen.getByText(caption)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull(); // neither the markup in the caption nor the pictures became elements
    expect(container.querySelector("[onerror]")).toBeNull();
  });

  it("has an empty state", () => {
    show(rankedVisual({ items: [], considered: 0 }));
    expect(screen.getByText("Not enough posts to rank yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("SentimentSummary (GR-38)", () => {
  it("shows the split, the counts and the top topics", () => {
    show(sentimentVisual());
    const section = screen.getByRole("region", { name: "Comment sentiment" });
    expect(within(section).getByText("comments made 1-22 Oct 2026")).toBeInTheDocument();
    expect(within(section).getByRole("img", { name: /Sentiment: 60 positive, 20 neutral, 10 negative/ })).toBeInTheDocument();
    const legend = within(section).getByRole("list", { name: "Comment counts" });
    expect(legend).toHaveTextContent("Positive 60");
    expect(legend).toHaveTextContent("Spam 5");
    expect(within(section).getByTestId("sentiment-pending")).toHaveTextContent("25 of 120 comments aren't analysed yet");
    const topics = within(section).getByRole("list", { name: "Top topics" });
    expect(topics).toHaveTextContent("price");
    expect(topics).toHaveTextContent("12 comments");
    expect(topics).toHaveTextContent("1 comment");
    expect(topics).not.toHaveTextContent("1 comments");
  });

  it("says when nothing is analysed yet, or there are no comments", () => {
    const { unmount } = show(sentimentVisual({ positive: 0, neutral: 0, negative: 0, spam: 0, not_analysed: 8, total: 8, topics: [] }));
    expect(screen.getByText("No analysed comments yet.")).toBeInTheDocument();
    expect(screen.queryByTestId("sentiment-bar")).toBeNull();
    unmount();
    show(sentimentVisual({ positive: 0, neutral: 0, negative: 0, spam: 0, not_analysed: 0, total: 0, topics: [] }));
    expect(screen.getByText("No comments to show.")).toBeInTheDocument();
  });

  it("draws a topic as text", () => {
    const { container } = show(sentimentVisual({ topics: [{ label: "<script>alert(1)</script>", count: 3 }] }));
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
  });
});

describe("VisualView (GR-38): a failing or unknown visual never takes the answer down", () => {
  it("hides a visual that throws and reports it with its kind", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const broken = { ...comparisonVisual(), metrics: null } as unknown as Visual;
    renderWithApi(
      <div>
        <p>The answer stays.</p>
        <VisualView visual={broken} slug="maple" />
      </div>,
    );
    expect(screen.getByText("The answer stays.")).toBeInTheDocument();
    expect(screen.queryByTestId("visual-metric-comparison")).toBeNull();
    expect(sentry.captureException).toHaveBeenCalledTimes(1);
    expect(sentry.captureException.mock.calls[0][1]).toMatchObject({ tags: { area: "agent_visual", visual_kind: "metric_comparison" } });
    spy.mockRestore();
  });

  it("draws nothing for a kind this build doesn't know (the API ahead of the web)", () => {
    const { container } = show({ kind: "pie_chart", version: 1, title: "x" } as unknown as Visual);
    expect(container.querySelector("[data-kind]")?.childElementCount).toBe(0);
    expect(sentry.captureException).not.toHaveBeenCalled();
  });

  it("marks each visual with its kind", () => {
    show(rankedVisual());
    expect(screen.getByTestId("visual")).toHaveAttribute("data-kind", "ranked_posts");
  });
});
