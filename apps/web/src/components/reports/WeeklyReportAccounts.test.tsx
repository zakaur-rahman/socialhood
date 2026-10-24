import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { BreakdownMetric, ReportAccount, WeeklyReport } from "@/lib/api/types";
import { json, problem, renderWithApi, type Call } from "@/test/api";

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

const IG = "11111111-1111-4111-8111-111111111111";
const WA = "22222222-2222-4222-8222-222222222222";
const ACCOUNTS: ReportAccount[] = [
  { id: IG, platform: "instagram", name: "Maple Bakery", username: "maple.bakery", status: "active" },
  { id: WA, platform: "whatsapp", name: "+91 98765", username: "+91 98765", status: "active" },
];

function series(values: (number | null)[]) {
  return values.map((value, i) => ({ week_start: `2026-08-${String(3 + i * 7).padStart(2, "0")}`, value }));
}

function count(key: BreakdownMetric["key"], label: string, value: number | null, previous: number | null, unavailable: string | null = null): BreakdownMetric {
  return {
    key,
    label,
    unit: "count",
    value,
    previous,
    change_pct: value !== null && previous ? Math.round(((value - previous) / previous) * 1000) / 10 : null,
    direction: value !== null && previous !== null ? (value >= previous ? "up" : "down") : null,
    unavailable,
    series: series(value === null ? [null, null, null, null, null, null, null, null] : [1, 2, 3, 4, 5, 6, previous ?? 0, value]),
  };
}

function report(overrides: Partial<WeeklyReport> = {}): WeeklyReport {
  return {
    week_start: "2026-09-21",
    week: { since: "2026-09-21", until: "2026-09-27", days: 7 },
    previous_week: { since: "2026-09-14", until: "2026-09-20", days: 7 },
    timezone: "Asia/Kolkata",
    weeks: ["2026-09-21", "2026-09-14"],
    series_weeks: 8,
    metrics: [
      {
        key: "messages_received",
        label: "Messages received",
        unit: "count",
        value: 142,
        previous: 120,
        change_pct: 18.3,
        change_points: null,
        direction: "up",
        lower_is_better: false,
        series: series([100, 110, 120, 125, 130, 118, 120, 142]),
      },
    ],
    account_metrics: [],
    account_comparison: {
      kind: "metric_comparison",
      version: 1,
      title: "All accounts: 21-27 Sep against 14-20 Sep",
      current: { label: "21-27 Sep", start: "2026-09-21", end: "2026-09-27", days: 7 },
      previous: { label: "14-20 Sep", start: "2026-09-14", end: "2026-09-20", days: 7 },
      comparable: true,
      note: null,
      account_label: null,
      metrics: [],
    },
    top_intents: [],
    top_posts: [],
    needs_you: 3,
    open_questions: 4,
    top_questions: [],
    accounts: ACCOUNTS,
    breakdown: [
      { account: ACCOUNTS[0], metrics: [count("messages_received", "Messages received", 90, 60), count("reach", "Reach", 5400, 5000)] },
      { account: ACCOUNTS[1], metrics: [count("messages_received", "Messages received", 52, 60), count("reach", "Reach", null, null, "insights_not_granted")] },
    ],
    ...overrides,
  };
}

function setup(options: { data?: WeeklyReport; byCall?: (call: Call) => Response | WeeklyReport } = {}) {
  return renderWithApi(<WeeklyReportPage />, {
    handlers: {
      "GET /v1/w/:wid/reports/weekly": (call) => {
        const found = options.byCall ? options.byCall(call) : (options.data ?? report());
        return found instanceof Response ? found : json(found);
      },
    },
  });
}

const asked = (calls: Call[]) => calls.find((c) => c.path.endsWith("/reports/weekly"))?.url.searchParams;

describe("the weekly report for one account or all of them", () => {
  it("has no picker for one account, and asks for every account without ?account=", async () => {
    const { calls } = setup({ data: report({ accounts: [ACCOUNTS[0]], breakdown: null }) });
    await screen.findByTestId("weekly-report");
    expect(screen.queryByRole("combobox", { name: "Account" })).toBeNull();
    expect(asked(calls)?.has("account_id")).toBe(false);
    expect(screen.queryByTestId("account-breakdown")).toBeNull();
  });

  it("lists All accounts and each account, and keeps the choice in the address next to the week", async () => {
    const user = userEvent.setup();
    search = "week=2026-09-14";
    setup({ data: report({ week_start: "2026-09-14" }) });
    await screen.findByTestId("weekly-report");
    await user.click(screen.getByRole("combobox", { name: "Account" }));
    expect(await screen.findByRole("option", { name: /All accounts/ })).toBeInTheDocument();
    await user.click(await screen.findByRole("option", { name: /\+91 98765/ }));
    expect(replace).toHaveBeenLastCalledWith(`/w/maple/reports?week=2026-09-14&account=${WA}`);
  });

  it("moving to another week keeps the account in the address", async () => {
    const user = userEvent.setup();
    search = `account=${WA}`;
    setup({ data: report({ week_start: "2026-09-21", account: ACCOUNTS[1], breakdown: null }) });
    await screen.findByTestId("weekly-report");
    await user.click(screen.getByRole("button", { name: "Earlier week" }));
    expect(replace).toHaveBeenLastCalledWith(`/w/maple/reports?week=2026-09-14&account=${WA}`);
  });

  it("asks the API for the account in the address and shows only that account in its own colour", async () => {
    search = `account=${WA}`;
    const { calls } = setup({ data: report({ account: ACCOUNTS[1], breakdown: null }) });
    expect(await screen.findByTestId("report-account")).toHaveTextContent("+91 98765");
    expect(asked(calls)?.get("account_id")).toBe(WA);
    expect(screen.queryByTestId("account-breakdown")).toBeNull();
    // The questions the AI couldn't answer belong to the workspace, so they are not in an account's report.
    expect(screen.queryByRole("link", { name: /questions the AI/ })).toBeNull();
    // The account keeps its place in the list as its colour: the second account is series 2.
    const tile = document.querySelector("[data-metric=messages_received]") as HTMLElement;
    expect(within(tile).getByTestId("series-line")).toHaveClass("stroke-chart-series-2");
  });

  it("ignores an ?account= that is not an id", async () => {
    search = "account=not-an-id";
    const { calls } = setup();
    await screen.findByTestId("weekly-report");
    expect(asked(calls)?.has("account_id")).toBe(false);
  });

  it("compares the accounts: a table, bars for this week against last and a line per account, one colour each", async () => {
    setup();
    const section = await screen.findByTestId("account-breakdown");
    const table = within(section).getByTestId("breakdown-table");
    const instagram = table.querySelector(`[data-account="${IG}"]`) as HTMLElement;
    const whatsapp = table.querySelector(`[data-account="${WA}"]`) as HTMLElement;
    expect(within(instagram).getByText("Maple Bakery")).toBeInTheDocument();
    expect(instagram.querySelector("[data-cell=messages_received]")).toHaveTextContent("90");
    expect(instagram.querySelector("[data-cell=messages_received]")).toHaveTextContent("+50%");
    expect(whatsapp.querySelector("[data-cell=messages_received]")).toHaveTextContent("52");
    // A figure the platform can't give is words, never 0.
    expect(whatsapp.querySelector("[data-cell=reach]")).toHaveTextContent("Not available: this account gives no insights");

    const card = section.querySelector("[data-breakdown=messages_received]") as HTMLElement;
    const bars = within(card).getAllByTestId("bar-current");
    expect(bars[0]).toHaveClass("bg-chart-series-1");
    expect(bars[1]).toHaveClass("bg-chart-series-2");
    const lines = within(card).getAllByTestId("series-line");
    expect(lines.map((l) => l.getAttribute("data-series"))).toEqual([IG, WA]);
    expect(lines[1]).toHaveClass("stroke-chart-series-2");
    // The reach card draws a line for the account that has readings only.
    const reach = section.querySelector("[data-breakdown=reach]") as HTMLElement;
    expect(within(reach).getAllByTestId("series-line")).toHaveLength(1);
  });

  it("explains an account that can't be shown and offers every account", async () => {
    search = `account=${WA}`;
    const user = userEvent.setup();
    setup({ byCall: () => problem(404, "not_found", "That account wasn't found.") });
    expect(await screen.findByText(/wasn.t found/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show every account, latest week" }));
    expect(replace).toHaveBeenLastCalledWith("/w/maple/reports");
  });
});
