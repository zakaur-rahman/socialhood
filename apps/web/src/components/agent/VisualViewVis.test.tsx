import { QueryClient } from "@tanstack/react-query";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "@/lib/api/queries/keys";
import type { AskInput, Visual } from "@/lib/api/types";
import { renderWithApi } from "@/test/api";
import { agentRun, runDetail } from "@/test/agent";
import { leadListVisual, leadRow, tableVisual, trendPoint, trendVisual } from "@/test/visuals";

import { RunView, type RunContext } from "./RunView";
import { VisualView } from "./VisualView";

const sentry = vi.hoisted(() => ({ captureException: vi.fn() }));
vi.mock("@sentry/nextjs", () => sentry);

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/w/maple/ask",
}));

function show(visual: Visual, props: { onNavigate?: () => void; onAsk?: (ask: AskInput) => void; busy?: boolean } = {}) {
  return renderWithApi(<VisualView visual={visual} slug="maple" {...props} />);
}

beforeEach(() => {
  sentry.captureException.mockReset();
});

describe("TrendChart (VIS-07)", () => {
  it("draws the API's points as lines, broken at a gap, labelled with the API's summary", () => {
    show(trendVisual());
    const section = screen.getByRole("region", { name: "Reach, 1-5 Oct 2026: @maple.bakery" });
    const svg = within(section).getByRole("img");
    expect(svg).toHaveAttribute("aria-label", trendVisual().summary);
    // 1-2 Oct and 4-5 Oct are two lines; 3 Oct has no reading, so nothing is drawn there.
    expect(within(section).getAllByTestId("trend-line")).toHaveLength(2);
    expect(within(section).getByTestId("trend-last")).toBeInTheDocument();
    expect(within(section).getByText("One point a day · +50% from the first reading")).toBeInTheDocument();
    expect(within(section).getByTestId("trend-gaps")).toHaveTextContent("4 of 5 days have a reading");
  });

  it("states the latest, lowest and highest as text, with their days", () => {
    show(trendVisual());
    const facts = screen.getByTestId("trend-facts");
    expect(facts).toHaveTextContent("Latest");
    expect(facts).toHaveTextContent("150");
    expect(facts).toHaveTextContent("Lowest");
    expect(facts).toHaveTextContent("90");
    expect(facts).toHaveTextContent("4 Oct");
  });

  it("has a text version of every point for screen readers, a gap as 'No reading' and never 0", () => {
    show(trendVisual());
    const table = screen.getByTestId("trend-table");
    expect(table).toHaveClass("sr-only");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(6); // header + 5 days
    expect(rows[3]).toHaveTextContent("3 Oct");
    expect(rows[3]).toHaveTextContent("No reading");
    expect(rows[3]).not.toHaveTextContent("0");
    expect(within(table).getByText(trendVisual().summary)).toBeInTheDocument();
  });

  it("uses the one chart colour token and scales with its column (375 px)", () => {
    show(trendVisual());
    const svg = screen.getByTestId("trend-svg");
    expect(svg.getAttribute("class")).toContain("text-chart-series-1");
    expect(svg.getAttribute("class")).toContain("w-full");
    expect(svg).toHaveAttribute("viewBox", "0 0 300 96");
    expect(svg.getAttribute("width")).toBeNull(); // no fixed pixel width to overflow a phone
  });

  it("a lone reading is a dot, and a series with none says so instead of drawing", () => {
    const points = [trendPoint(1, null), trendPoint(2, 40), trendPoint(3, null)];
    const { unmount } = show(trendVisual({ points, known_points: 1, first: points[1], last: points[1], lowest: points[1], highest: points[1], change_pct: null, direction: null }));
    expect(screen.getByTestId("trend-dot")).toBeInTheDocument();
    expect(screen.queryByTestId("trend-line")).toBeNull();
    unmount();
    const none = [trendPoint(1, null), trendPoint(2, null)];
    show(trendVisual({ points: none, known_points: 0, first: null, last: null, lowest: null, highest: null, change_pct: null, direction: null }));
    expect(screen.getByText("No readings in this period, so there is nothing to draw.")).toBeInTheDocument();
    expect(screen.queryByTestId("trend-svg")).toBeNull();
  });

  it("a weekly trend says so", () => {
    show(trendVisual({ granularity: "week" }));
    expect(screen.getByText(/One point a week/)).toBeInTheDocument();
    expect(screen.getByText("Week of 1 Oct")).toBeInTheDocument();
  });
});

describe("LeadList (VIS-08, VIS-12)", () => {
  it("lists the leads in the API's order with their scores, each linking to its conversation", async () => {
    const onNavigate = vi.fn();
    show(leadListVisual(), { onNavigate });
    const section = screen.getByRole("region", { name: "Leads waiting for your reply" });
    expect(within(section).getByText("5 leads are waiting, best score first")).toBeInTheDocument();
    const rows = within(section).getAllByTestId("lead-row");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Priya Shah");
    expect(rows[0]).toHaveTextContent("Instagram · 2 hours ago");
    expect(within(rows[0]).getByTestId("lead-score")).toHaveTextContent("Score 90");
    expect(within(rows[1]).getByTestId("lead-score")).toHaveTextContent("Score 60");
    expect(rows[1]).toHaveTextContent("Qualified");
    const link = within(rows[0]).getByRole("link");
    expect(link).toHaveAttribute("href", "/w/maple/inbox/cv1");
    link.addEventListener("click", (event) => event.preventDefault());
    await userEvent.click(link);
    expect(onNavigate).toHaveBeenCalled();
  });

  it("a lead without a score reads 'No score', and one who never wrote opens the Contacts page", () => {
    show(leadListVisual());
    const row = screen.getAllByTestId("lead-row")[2];
    expect(within(row).getByTestId("lead-score")).toHaveTextContent("No score");
    expect(within(row).getByTestId("lead-score")).not.toHaveTextContent("0");
    expect(within(row).getByRole("link")).toHaveAttribute("href", "/w/maple/contacts");
  });

  it("says how many more wait and links to the full list", () => {
    show(leadListVisual());
    const more = screen.getByTestId("lead-more");
    expect(more).toHaveTextContent("+2 more");
    expect(within(more).getByRole("link")).toHaveAttribute("href", "/w/maple/inbox?view=needs_reply");
  });

  it("an unsafe 'more' link is shown as text, not a link; nothing more means no line", () => {
    const { unmount } = show(leadListVisual({ more_route: "https://evil.example/x" }));
    const more = screen.getByTestId("lead-more");
    expect(more).toHaveTextContent("+2 more");
    expect(within(more).queryByRole("link")).toBeNull();
    unmount();
    show(leadListVisual({ total: 3 }));
    expect(screen.queryByTestId("lead-more")).toBeNull();
  });

  it("draws a customer's name as text", () => {
    const name = "<img src=x onerror=alert(1)> Priya";
    const { container } = show(leadListVisual({ items: [leadRow({ name })] }));
    expect(screen.getByText(name)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
  });

  it("has an empty state", () => {
    show(leadListVisual({ items: [], total: 0, reply_ids: [] }));
    expect(screen.getByText("Nobody is waiting for a reply.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Prepare replies" })).toBeNull();
  });

  it("Prepare replies asks the agent for a draft per conversation the API chose, and says nothing is sent", async () => {
    const onAsk = vi.fn();
    show(leadListVisual(), { onAsk });
    expect(screen.getByText("Drafts a reply for the top 2 leads. Nothing is sent.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Prepare replies" }));
    expect(onAsk).toHaveBeenCalledTimes(1);
    // A structured hint with ids only: the API words the question, so no ids or customer text show.
    expect(onAsk.mock.calls[0][0]).toEqual({ reply_conversation_ids: ["cv1", "cv2"] });
  });

  it("offers no follow-up on an older answer, or when the API chose no conversation", () => {
    const { unmount } = show(leadListVisual());
    expect(screen.queryByRole("button", { name: "Prepare replies" })).toBeNull();
    unmount();
    show(leadListVisual({ reply_ids: [] }), { onAsk: vi.fn() });
    expect(screen.queryByRole("button", { name: "Prepare replies" })).toBeNull();
  });

  it("the button waits while a question is being sent", () => {
    show(leadListVisual(), { onAsk: vi.fn(), busy: true });
    expect(screen.getByRole("button", { name: "Prepare replies" })).toBeDisabled();
  });
});

describe("DataTableVisual (VIS-09)", () => {
  it("draws the columns and cells, right-aligning figures and showing a missing cell as a dash", () => {
    show(tableVisual());
    const section = screen.getByRole("region", { name: "Orders" });
    expect(within(section).getByText("14 rows, 2 shown")).toBeInTheDocument();
    const headers = within(section).getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual(["Order", "Customer", "Total", "Score"]);
    expect(headers[2].className).toContain("text-right");
    expect(headers[0].className).not.toContain("text-right");
    const rows = within(section).getAllByTestId("table-row");
    expect(rows).toHaveLength(2);
    const first = within(rows[0]).getAllByRole("cell");
    expect(first.map((c) => c.textContent)).toEqual(["#12", "@priya", "INR 1598.00", "82"]);
    expect(first[2].className).toContain("text-right");
    expect(first[2].className).toContain("tabular-nums");
    const second = within(rows[1]).getAllByRole("cell");
    expect(second.map((c) => c.textContent)).toEqual(["#11", "—", "INR 799.00", "—"]);
  });

  it("links '+N more' to the full page when there is one", () => {
    show(tableVisual());
    const more = screen.getByTestId("table-more");
    expect(more).toHaveTextContent("+12 more");
    expect(within(more).getByRole("link")).toHaveAttribute("href", "/w/maple/orders");
  });

  it("shows '+N more' as plain text without a safe page, and nothing when all rows are shown", () => {
    const { unmount } = show(tableVisual({ more_route: null }));
    expect(within(screen.getByTestId("table-more")).queryByRole("link")).toBeNull();
    unmount();
    show(tableVisual({ total: 2 }));
    expect(screen.queryByTestId("table-more")).toBeNull();
  });

  it("draws a customer's words as text and has an empty state", () => {
    const words = "<script>alert(1)</script>";
    const { container, unmount } = show(tableVisual({ rows: [{ cells: ["#1", words, "INR 1.00", 1] }], total: 1 }));
    expect(screen.getByText(words)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    unmount();
    show(tableVisual({ rows: [], total: 0 }));
    expect(screen.getByText("Nothing to show.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("visuals while the run is working (VIS-10)", () => {
  const context: RunContext = {
    wid: "w1",
    slug: "maple",
    timeZone: "Asia/Kolkata",
    role: "owner",
    now: new Date("2026-09-29T10:00:00Z"),
  };

  it("shows a visual the moment its step has produced it, before there is an answer", () => {
    const queryClient = new QueryClient();
    const run = agentRun({ id: "r1", status: "running" });
    queryClient.setQueryData(keys.agentRun("w1", "r1"), runDetail({ ...run, steps: [], visuals: [trendVisual()] }));
    renderWithApi(<RunView run={run} context={context} latest />, { queryClient });
    expect(screen.getByTestId("run-visuals")).toBeInTheDocument();
    expect(screen.getByTestId("visual-trend")).toBeInTheDocument();
    expect(screen.queryByTestId("run-result")).toBeNull(); // no answer yet
  });

  it("a running run without a visual shows only its steps", () => {
    const queryClient = new QueryClient();
    const run = agentRun({ id: "r1", status: "running" });
    queryClient.setQueryData(keys.agentRun("w1", "r1"), runDetail({ ...run, steps: [], visuals: [] }));
    renderWithApi(<RunView run={run} context={context} latest />, { queryClient });
    expect(screen.queryByTestId("run-visuals")).toBeNull();
  });

  it("only the latest finished answer offers the lead list's follow-up", async () => {
    const onAsk = vi.fn();
    const run = agentRun({ id: "r1", status: "succeeded", answer: "Three leads wait.", visuals: [leadListVisual()] });
    const { unmount } = renderWithApi(<RunView run={run} context={{ ...context, onAsk }} latest />);
    await userEvent.click(screen.getByRole("button", { name: "Prepare replies" }));
    expect(onAsk).toHaveBeenCalledTimes(1);
    unmount();
    renderWithApi(<RunView run={run} context={{ ...context, onAsk }} latest={false} />);
    expect(screen.queryByRole("button", { name: "Prepare replies" })).toBeNull();
  });
});

describe("VisualView (VIS-07 to VIS-09): the new kinds are boundary-wrapped like the rest", () => {
  it("hides a lead list that throws and reports it with its kind", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const broken = { ...leadListVisual(), items: null } as unknown as Visual;
    renderWithApi(
      <div>
        <p>The answer stays.</p>
        <VisualView visual={broken} slug="maple" />
      </div>,
    );
    expect(screen.getByText("The answer stays.")).toBeInTheDocument();
    expect(screen.queryByTestId("visual-lead-list")).toBeNull();
    expect(sentry.captureException.mock.calls[0][1]).toMatchObject({ tags: { area: "agent_visual", visual_kind: "lead_list" } });
    spy.mockRestore();
  });

  it("marks each with its kind", () => {
    const { unmount } = show(trendVisual());
    expect(screen.getByTestId("visual")).toHaveAttribute("data-kind", "trend");
    unmount();
    show(tableVisual());
    expect(screen.getByTestId("visual")).toHaveAttribute("data-kind", "table");
  });
});

describe("range and platform controls (VIS-11)", () => {
  const credits = (used: number, limit: number | null = 200) => ({ limit, used, resetsOn: "2026-11-01" });

  it("offers range and platform under a trend on the latest answer, with what a change costs", () => {
    show(trendVisual({ period: { start: "2026-09-01", end: "2026-09-30", label: "1-30 Sep 2026", days: 30 } }), {
      onAsk: vi.fn(),
    });
    const controls = screen.getByTestId("visual-controls");
    expect(within(controls).getByRole("radio", { name: "Last 30 days" })).toBeChecked();
    expect(within(controls).getByRole("radio", { name: "Instagram" })).not.toBeChecked();
    expect(within(controls).getByTestId("controls-note")).toHaveTextContent(
      "Changing this asks again. About 2 to 4 AI credits."
    );
  });

  it("has no controls on an older answer or on a visual with no range to change", () => {
    const { unmount } = show(trendVisual());
    expect(screen.queryByTestId("visual-controls")).toBeNull();
    unmount();
    show(tableVisual(), { onAsk: vi.fn() });
    expect(screen.queryByTestId("visual-controls")).toBeNull();
  });

  it("choosing a range asks the same question as a structured follow-up, never a data query", async () => {
    const onAsk = vi.fn();
    show(trendVisual(), { onAsk });
    await userEvent.click(screen.getByRole("radio", { name: "Last 90 days" }));
    expect(onAsk).toHaveBeenCalledWith({ range_days: 90 });
    await userEvent.click(screen.getByRole("radio", { name: "Instagram" }));
    // The platform change keeps the range already chosen on the screen (none: the 5-day period).
    expect(onAsk).toHaveBeenLastCalledWith({ platform: "instagram" });
  });

  it("keeps the other control's choice from the run's own follow-up", async () => {
    const onAsk = vi.fn();
    renderWithApi(
      <VisualView visual={trendVisual()} slug="maple" onAsk={onAsk} runHints={{ range_days: 7, platform: "facebook" }} />
    );
    await userEvent.click(screen.getByRole("radio", { name: "Instagram" }));
    expect(onAsk).toHaveBeenCalledWith({ range_days: 7, platform: "instagram" });
  });

  it("explains instead of failing when the credits are used up or too few", () => {
    const { unmount } = renderWithApi(
      <VisualView visual={trendVisual()} slug="maple" onAsk={vi.fn()} credits={credits(200)} />
    );
    expect(screen.getByTestId("controls-note")).toHaveTextContent("You've used all 200 AI credits for this month.");
    expect(screen.getByRole("radio", { name: "Last 30 days" })).toBeDisabled();
    unmount();
    renderWithApi(<VisualView visual={trendVisual()} slug="maple" onAsk={vi.fn()} credits={credits(198)} />);
    expect(screen.getByTestId("controls-note")).toHaveTextContent("You have 2 AI credits left this month");
  });

  it("waits while a question is being sent", () => {
    show(trendVisual(), { onAsk: vi.fn(), busy: true });
    expect(screen.getByRole("radio", { name: "Last 7 days" })).toBeDisabled();
  });
});
