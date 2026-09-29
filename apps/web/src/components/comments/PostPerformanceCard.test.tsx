import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import type { AgeName, PostComparison, PostPerformance } from "@/lib/api/types";
import { account, comparison, json, performance, problem, renderWithApi, type Call } from "@/test/api";

import { PostPerformanceCard } from "./PostPerformanceCard";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

type Answers = {
  perf?: (age: AgeName | null) => PostPerformance | Response;
  compare?: (age: AgeName | null) => PostComparison | Response;
};

function setup({ perf = () => performance(), compare = () => comparison() }: Answers = {}) {
  const asked: { path: string; age: string | null }[] = [];
  const answer = (value: object | Response) => (value instanceof Response ? value : json(value));
  const record = (call: Call) => {
    const age = call.url.searchParams.get("age");
    asked.push({ path: call.path.split("/").pop()!, age });
    return age as AgeName | null;
  };
  const view = renderWithApi(
    <PostPerformanceCard
      wid="w1"
      postId="po1"
      account={account()}
      slug="maple"
      timeZone="Asia/Kolkata"
      now={new Date("2026-09-29T08:00:00Z")}
    />,
    {
      handlers: {
        "GET /v1/w/:wid/analytics/posts/:id/performance": (call) => answer(perf(record(call))),
        "GET /v1/w/:wid/analytics/posts/:id/compare": (call) => answer(compare(record(call))),
      },
    },
  );
  return { ...view, asked };
}

function figure(label: string): string {
  const term = screen.getByText(label, { selector: "dt" });
  return term.nextElementSibling?.textContent ?? "";
}

describe("Post figures (FR-ANL-02)", () => {
  it("shows reach, views, likes, comments, shares, saves and engagement rate with the age used", async () => {
    const { asked } = setup();
    await screen.findByTestId("post-figures");
    expect(screen.getByTestId("figures-age")).toHaveTextContent("Figures at 24 h after posting · Read Yesterday 17:35");
    expect(figure("Reach")).toBe("1,240");
    expect(figure("Views")).toBe("3,100");
    expect(figure("Likes")).toBe("180");
    expect(figure("Comments")).toBe("12");
    expect(figure("Shares")).toBe("9");
    expect(figure("Saves")).toBe("21");
    expect(figure("Engagement rate")).toBe("17.8%");
    // the latest window was asked for (no age), and the selector shows the one the API used
    expect(asked).toEqual(
      expect.arrayContaining([
        { path: "performance", age: null },
        { path: "compare", age: null },
      ]),
    );
    expect(screen.getByRole("combobox", { name: "Age after posting" })).toHaveTextContent("At 24 h");
    expect(screen.getByText("Instagram can take up to 48 h to settle these numbers.")).toBeInTheDocument();
  });

  it("the age selector asks for that age; a younger post says which age it is shown at", async () => {
    const user = userEvent.setup();
    const { asked } = setup({
      perf: (age) => performance(age ? { requested_age: age, age: "24h" } : {}),
      compare: (age) => comparison(age ? { post: performance({ requested_age: age, age: "24h" }) } : {}),
    });
    await screen.findByTestId("post-figures");

    await user.click(screen.getByRole("combobox", { name: "Age after posting" }));
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "At 1 h",
      "At 6 h",
      "At 24 h",
      "At 72 h",
      "At 7 d",
      "At 30 d",
      "Lifetime",
    ]);
    await user.click(screen.getByRole("option", { name: "At 7 d" }));

    expect(await screen.findByText("This post hasn't reached 7 d yet, so these are its figures at 24 h.")).toBeInTheDocument();
    expect(await screen.findByText("This post hasn't reached 7 d yet, so it's compared at 24 h.")).toBeInTheDocument();
    expect(asked).toEqual(
      expect.arrayContaining([
        { path: "performance", age: "7d" },
        { path: "compare", age: "7d" },
      ]),
    );
    expect(screen.getByRole("combobox", { name: "Age after posting" })).toHaveTextContent("At 7 d");
  });

  it("insights not granted: says so, offers Reconnect, and shows unknown figures as —", async () => {
    setup({
      perf: () =>
        performance({
          insights_granted: false,
          metrics: { reach: null, views: null, likes: 180, comments: 12, shares: null, saves: null, engagement_rate: null },
        }),
    });
    const notice = await screen.findByTestId("insights-unavailable");
    expect(notice).toHaveTextContent(
      "@maple.bakery didn't give Social Hood permission to read insights, so reach, views, shares and saves aren't available. Reconnect to allow it.",
    );
    expect(within(notice).getByRole("link", { name: "Reconnect" })).toHaveAttribute("href", "/w/maple/settings/connections");
    expect(figure("Reach")).toBe("—");
    expect(figure("Engagement rate")).toBe("—");
    expect(figure("Likes")).toBe("180");
    expect(screen.queryByText("Instagram can take up to 48 h to settle these numbers.")).not.toBeInTheDocument();
  });

  it("before the first snapshot: no figures yet, and when they will come", async () => {
    setup({ perf: () => performance({ captured_at: null, age: "1h", metrics: {} }) });
    expect(await screen.findByTestId("no-figures")).toHaveTextContent("No figures yet");
    expect(screen.getByTestId("no-figures")).toHaveTextContent("1 h, 6 h, 24 h, 72 h, 7 days and 30 days");
  });

  it("a failed load offers Try again", async () => {
    const user = userEvent.setup();
    let fail = true;
    setup({ perf: () => (fail ? problem(503, "platform_unavailable") : performance()) });
    const retry = await screen.findAllByRole("button", { name: "Try again" });
    fail = false;
    await user.click(retry[0]);
    expect(await screen.findByTestId("post-figures")).toBeInTheDocument();
  });
});

describe("Comparison at the same age (TR-AGT-05, agent-architecture §6)", () => {
  it("enough history: the baseline size and each metric's difference from the median", async () => {
    setup();
    expect(await screen.findByTestId("baseline")).toHaveTextContent("Compared with 8 earlier feed posts (of the last 10) at 24 h");
    const rows = within(screen.getByRole("list", { name: "Difference from the median" })).getAllByRole("listitem");
    expect(rows.map((row) => row.dataset.metric)).toEqual([
      "reach",
      "views",
      "likes",
      "comments",
      "shares",
      "saves",
      "engagement_rate",
    ]);
    const reach = rows[0];
    expect(reach).toHaveTextContent("1,240 vs median 1,050");
    expect(within(reach).getByText("+18.1%")).toBeInTheDocument();
    expect(within(reach).getByText("18.1% above the median")).toHaveClass("sr-only");
    expect(reach.querySelector("[data-tone]")).toHaveAttribute("data-tone", "up");

    expect(within(rows[1]).getByText("−8.8%")).toBeInTheDocument();
    expect(rows[1].querySelector("[data-tone]")).toHaveAttribute("data-tone", "down");
    expect(within(rows[2]).getByText("0%")).toBeInTheDocument();
    // no median above 0: no difference, and the smaller sample is stated
    expect(rows[4]).toHaveTextContent("9 vs median 0 of 6 posts");
    expect(within(rows[4]).getByText("—")).toBeInTheDocument();
    expect(rows[6]).toHaveTextContent("17.8% vs median 15.2%");
  });

  it("fewer than 3 comparable posts: not enough history, and no conclusion", async () => {
    setup({ compare: () => comparison({ enough_history: false, baseline_size: 2 }) });
    const box = await screen.findByTestId("not-enough-history");
    expect(box).toHaveTextContent("Not enough history");
    expect(box).toHaveTextContent("Only 2 earlier feed posts have figures at 24 h. Comparisons need at least 3.");
    expect(screen.queryByRole("list", { name: "Difference from the median" })).not.toBeInTheDocument();
    expect(screen.queryByText("+18.1%")).not.toBeInTheDocument();
  });

  it("Reels are compared with Reels", async () => {
    setup({ compare: () => comparison({ post: performance({ media_type: "reel" }), baseline_size: 5 }) });
    expect(await screen.findByTestId("baseline")).toHaveTextContent("Compared with 5 earlier Reels (of the last 10) at 24 h");
  });

  it("the comparison waits for its own answer and fails on its own", async () => {
    setup({ compare: () => problem(500, "internal") });
    await screen.findByTestId("post-figures");
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByTestId("post-figures")).toBeInTheDocument();
  });
});
