import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { ReportMetric, WeeklyReport } from "@/lib/api/types";
import { json, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { WeeklyReportPage } from "./WeeklyReportPage";

const replace = vi.fn();
let search = "";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/reports",
  useSearchParams: () => new URLSearchParams(search),
}));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

beforeEach(() => {
  replace.mockClear();
  search = "";
});

const MONDAYS = ["2026-09-21", "2026-09-14", "2026-09-07", "2026-08-31"];

function series(values: (number | null)[]) {
  return values.map((value, i) => ({ week_start: `2026-08-${String(3 + i * 7).padStart(2, "0")}`, value }));
}

function metric(key: ReportMetric["key"], label: string, values: Partial<ReportMetric> = {}): ReportMetric {
  return {
    key,
    label,
    unit: "count",
    value: 142,
    previous: 120,
    change_pct: 18.3,
    change_points: null,
    direction: "up",
    lower_is_better: false,
    series: series([100, 110, 120, 125, 130, 118, 120, 142]),
    ...values,
  };
}

function report(overrides: Partial<WeeklyReport> = {}): WeeklyReport {
  return {
    week_start: "2026-09-21",
    week: { since: "2026-09-21", until: "2026-09-27", days: 7 },
    previous_week: { since: "2026-09-14", until: "2026-09-20", days: 7 },
    timezone: "Asia/Kolkata",
    weeks: MONDAYS,
    series_weeks: 8,
    metrics: [
      metric("messages_received", "Messages received"),
      metric("reply_rate", "Reply rate", { unit: "percent", value: 88.4, previous: 91, change_pct: null, change_points: -2.6, direction: "down" }),
      metric("median_first_response_s", "Median first response", {
        unit: "seconds",
        value: null,
        previous: null,
        change_pct: null,
        direction: null,
        lower_is_better: true,
        series: series([null, null, null, null, null, null, null, null]),
      }),
      metric("captures", "Leads captured", { value: 14, previous: 10, change_pct: 40, direction: "up" }),
      metric("leads_won", "Leads won", { value: 2, previous: 0, change_pct: null, direction: "up", series: series([null, null, 0, 0, 1, 0, 0, 2]) }),
    ],
    account_metrics: [
      {
        label: "Reach",
        figure: {
          metric: "reach",
          current: { value: 5400, days_known: 5, days_total: 7 },
          previous: { value: 5000, days_known: 7, days_total: 7 },
          change_pct: 8,
          direction: "up",
        },
        series: series([null, null, null, null, 4800, 5000, 5000, 5400]),
      },
      {
        label: "Views",
        figure: {
          metric: "views",
          current: { value: null, days_known: 0, days_total: 7, unavailable: "no_readings" },
          previous: { value: null, days_known: 0, days_total: 7, unavailable: "no_readings" },
        },
        series: series([null, null, null, null, null, null, null, null]),
      },
    ],
    account_comparison: {
      kind: "metric_comparison",
      version: 1,
      title: "All accounts: 21–27 Sep against 14–20 Sep",
      current: { label: "21–27 Sep", start: "2026-09-21", end: "2026-09-27", days: 7 },
      previous: { label: "14–20 Sep", start: "2026-09-14", end: "2026-09-20", days: 7 },
      comparable: true,
      note: null,
      account_label: null,
      metrics: [
        {
          key: "reach",
          label: "Reach",
          format: "count",
          current: 5400,
          previous: 5000,
          change_pct: 8,
          direction: "up",
          tone: "good",
          current_coverage: "5 of 7 days",
          previous_coverage: null,
          unavailable: null,
        },
        {
          key: "views",
          label: "Views",
          format: "count",
          current: null,
          previous: null,
          change_pct: null,
          direction: null,
          tone: "neutral",
          current_coverage: null,
          previous_coverage: null,
          unavailable: "No daily figures are recorded for these days yet.",
        },
      ],
    },
    top_intents: [
      { intent: "pricing", count: 32 },
      { intent: "shipping", count: 18 },
    ],
    top_posts: [{ id: "p1", caption: "New autumn cakes are here\nOrder by Friday", permalink: null, posted_at: "2026-09-20T12:00:00Z", comments: 24 }],
    needs_you: 3,
    open_questions: 4,
    top_questions: [{ topic: "Do you ship to Dubai?", asked: 5 }],
    ...overrides,
  };
}

function setup(options: { data?: WeeklyReport; byWeek?: (call: Call) => Response | WeeklyReport } = {}) {
  return renderWithApi(<WeeklyReportPage />, {
    handlers: {
      "GET /v1/w/:wid/reports/weekly": (call) => {
        const found = options.byWeek ? options.byWeek(call) : (options.data ?? report());
        return found instanceof Response ? found : json(found);
      },
    },
  });
}

function item(key: string): HTMLElement {
  return document.querySelector(`[data-metric="${key}"]`) as HTMLElement;
}

function accountItem(key: string): HTMLElement {
  return document.querySelector(`[data-account-metric="${key}"]`) as HTMLElement;
}

describe("the weekly report page (GR-34)", () => {
  it("shows the week, a tile per count with the API's change, and a chart under each", async () => {
    setup();
    expect(await screen.findByRole("heading", { level: 1, name: "Weekly report" })).toBeInTheDocument();
    expect(await screen.findByTestId("report-span")).toHaveTextContent("21–27 Sep, Monday to Sunday in Asia/Kolkata, against 14–20 Sep");

    const messages = item("messages_received");
    expect(within(messages).getByTestId("metric-value")).toHaveTextContent("142");
    expect(within(messages).getByTestId("trend")).toHaveTextContent("+18.3%");
    expect(within(messages).getByText("Week before: 120")).toBeInTheDocument();
    expect(within(messages).getByTestId("series-chart")).toBeInTheDocument();

    const rate = item("reply_rate");
    expect(within(rate).getByTestId("metric-value")).toHaveTextContent("88.4%");
    expect(within(rate).getByTestId("trend")).toHaveTextContent("−2.6 pts");
    expect(within(rate).getByTestId("trend")).toHaveAttribute("data-tone", "bad");
  });

  it("a metric with nothing in any week is one line of words, not a card with a flat chart", async () => {
    setup();
    await screen.findByTestId("weekly-report");
    // The median first response has no value in all 8 weeks.
    expect(item("median_first_response_s")).toBeNull();
    expect(screen.getByTestId("report-idle")).toHaveTextContent("No activity in the last 8 weeks: Median first response.");
    // The others keep their card.
    expect(item("messages_received")).not.toBeNull();
  });

  it("a rise from nothing is New, and a line that starts mid-chart says where", async () => {
    setup();
    const won = await waitFor(() => {
      const found = item("leads_won");
      expect(found).not.toBeNull();
      return found;
    });
    expect(within(won).getByTestId("trend")).toHaveTextContent("New");
    expect(within(won).getByTestId("series-gaps")).toHaveTextContent("No data before 17 Aug");
  });

  it("keeps each chart inside its tile, so the card grows to hold it", async () => {
    setup();
    await screen.findByTestId("weekly-report");
    const tile = within(item("messages_received")).getByTestId("metric-tile");
    expect(within(tile).getByTestId("series-chart")).toBeInTheDocument();
  });

  it("writes a small change out instead of calling it No change", async () => {
    const followers = {
      label: "Followers",
      figure: {
        metric: "followers" as const,
        current: { value: 1054, days_known: 7, days_total: 7 },
        previous: { value: 1056, days_known: 7, days_total: 7 },
        change_pct: -0.2,
        direction: "flat" as const,
      },
      series: series([1050, 1051, 1052, 1053, 1056, 1056, 1056, 1054]),
    };
    setup({ data: report({ account_metrics: [followers] }) });
    const tile = await waitFor(() => {
      const found = accountItem("followers");
      expect(found).not.toBeNull();
      return found;
    });
    expect(within(tile).getByTestId("trend")).toHaveTextContent("−2 (−0.2%)");
    expect(within(tile).getByTestId("trend")).not.toHaveTextContent("No change");
    expect(within(tile).getByText("Week before: 1,056")).toBeInTheDocument();
  });

  it("the account insights are tiles with one clear line, and the ones without readings are one sentence", async () => {
    setup();
    const reach = await waitFor(() => {
      const found = accountItem("reach");
      expect(found).not.toBeNull();
      return found;
    });
    expect(within(reach).getByTestId("metric-value")).toHaveTextContent("5,400");
    expect(within(reach).getByText("Week before: 5,000 · readings on 5 of 7 days, 7 of 7 days the week before")).toBeInTheDocument();
    expect(within(reach).getByTestId("series-chart")).toBeInTheDocument();
    expect(accountItem("views")).toBeNull();
    expect(screen.getByTestId("insights-idle")).toHaveTextContent("No readings in these weeks: Views.");
  });

  it("shows intents, posts and what is open now", async () => {
    setup();
    await screen.findByTestId("weekly-report");
    expect(screen.getByText("Pricing")).toBeInTheDocument();
    expect(screen.getByText("32 messages")).toBeInTheDocument();
    const post = screen.getByRole("link", { name: "New autumn cakes are here" });
    expect(post).toHaveAttribute("href", "/w/maple/comments/p1");
    expect(screen.getByText("24 comments")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /3\s+conversations need you/ })).toHaveAttribute("href", "/w/maple/inbox");
    expect(screen.getByRole("link", { name: /4\s+questions the AI couldn't answer/ })).toHaveAttribute("href", "/w/maple/knowledge");
    expect(screen.getByText("Do you ship to Dubai?")).toBeInTheDocument();
  });

  it("counts the leads captured in flows, against the week before, with no note about it", async () => {
    setup();
    await screen.findByTestId("weekly-report");
    const captured = item("captures");
    expect(captured).toHaveTextContent("Leads captured");
    expect(captured).toHaveTextContent("14");
    expect(within(captured).getByTestId("trend")).toHaveTextContent("+40");
    expect(screen.queryByTestId("report-note")).toBeNull();
    expect(screen.queryByText(/aren't counted here yet/)).toBeNull();
  });
});

describe("the week in the address and the picker", () => {
  it("asks for the latest week without a week in the address", async () => {
    const { calls } = setup();
    await screen.findByTestId("weekly-report");
    const call = calls.find((c) => c.path.endsWith("/reports/weekly"));
    expect(call?.url.searchParams.has("week")).toBe(false);
  });

  it("asks for the week in the address, and ignores a value that isn't a date", async () => {
    search = "week=2026-09-14";
    const first = setup({ data: report({ week_start: "2026-09-14" }) });
    await screen.findByTestId("weekly-report");
    expect(first.calls.find((c) => c.path.endsWith("/reports/weekly"))?.url.searchParams.get("week")).toBe("2026-09-14");
    first.unmount();

    search = "week=last-tuesday";
    const second = setup();
    await screen.findByTestId("weekly-report");
    expect(second.calls.find((c) => c.path.endsWith("/reports/weekly"))?.url.searchParams.has("week")).toBe(false);
  });

  it("goes to an earlier or later week through the address", async () => {
    const user = userEvent.setup();
    setup({ data: report({ week_start: "2026-09-14" }) });
    await screen.findByTestId("weekly-report");
    await user.click(screen.getByRole("button", { name: "Earlier week" }));
    expect(replace).toHaveBeenLastCalledWith("/w/maple/reports?week=2026-09-07");
    await user.click(screen.getByRole("button", { name: "Later week" }));
    expect(replace).toHaveBeenLastCalledWith("/w/maple/reports?week=2026-09-21");
  });

  it("can't go later than the latest week or earlier than the oldest one listed", async () => {
    const { unmount } = setup();
    await screen.findByTestId("weekly-report");
    expect(screen.getByRole("button", { name: "Later week" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Earlier week" })).toBeEnabled();
    unmount();
    setup({ data: report({ week_start: "2026-08-31" }) });
    await screen.findByTestId("weekly-report");
    expect(screen.getByRole("button", { name: "Earlier week" })).toBeDisabled();
  });

  it("picks a week from the list", async () => {
    const user = userEvent.setup();
    setup();
    await screen.findByTestId("weekly-report");
    await user.click(screen.getByRole("combobox", { name: "Week" }));
    await user.click(await screen.findByRole("option", { name: "Week of 7 Sep" }));
    expect(replace).toHaveBeenLastCalledWith("/w/maple/reports?week=2026-09-07");
  });
});

describe("loading and failing", () => {
  it("says it is loading", () => {
    renderWithApi(<WeeklyReportPage />, {
      handlers: { "GET /v1/w/:wid/reports/weekly": () => new Promise<Response>(() => {}) },
    });
    expect(screen.getByRole("status", { name: "Loading the weekly report" })).toBeInTheDocument();
  });

  it("explains a week that can't be shown and offers the latest one", async () => {
    search = "week=2026-09-22";
    const user = userEvent.setup();
    setup({ byWeek: () => problem(422, "validation_error", "That isn't a week the report can show.") });
    expect(await screen.findByText(/isn.t a week the report can show/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show the latest week" }));
    expect(replace).toHaveBeenLastCalledWith("/w/maple/reports");
  });

  it("offers Try again when the report can't load", async () => {
    setup({ byWeek: () => problem(500, "internal") });
    expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show the latest week" })).toBeNull();
  });

  it("works for an agent too (any member reads it)", async () => {
    renderWithApi(<WeeklyReportPage />, {
      ws: { ...workspace, role: "agent" },
      handlers: { "GET /v1/w/:wid/reports/weekly": () => json(report()) },
    });
    expect(await screen.findByTestId("weekly-report")).toBeInTheDocument();
  });
});
