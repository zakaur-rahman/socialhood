import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SeriesChart } from "./SeriesChart";

const week = (day: number, value: number | null) => ({ week_start: `2026-09-${String(day).padStart(2, "0")}`, value });

describe("SeriesChart (GR-34)", () => {
  it("draws one line in the series colour and a dot on the latest week", () => {
    render(<SeriesChart label="Messages received" unit="count" series={[week(7, 3), week(14, 5), week(21, 9)]} />);
    expect(screen.getAllByTestId("series-line")).toHaveLength(1);
    expect(screen.getByTestId("series-line")).toHaveClass("stroke-chart-series-1");
    expect(screen.getByTestId("series-last")).toHaveClass("bg-chart-series-1");
    expect(screen.queryByTestId("series-gaps")).toBeNull();
    // The first and last week sit under it as text.
    expect(screen.getByText("7 Sep")).toBeInTheDocument();
    expect(screen.getByText("21 Sep")).toBeInTheDocument();
  });

  it("takes the colour of the entity it is for", () => {
    render(<SeriesChart label="Reach" unit="count" color={2} series={[week(7, 3), week(14, 5)]} />);
    expect(screen.getByTestId("series-line")).toHaveClass("stroke-chart-series-3");
  });

  it("has every week in a table, gaps included", () => {
    render(<SeriesChart label="Reach" unit="count" series={[week(7, 12), week(14, null), week(21, 1204)]} />);
    const table = screen.getByRole("table", { name: "Reach by week" });
    const rows = within(table).getAllByRole("row").map((row) => row.textContent);
    expect(rows).toEqual(["WeekReach", "Week of 7 Sep12", "Week of 14 SepNo data", "Week of 21 Sep1,204"]);
  });

  it("breaks the line at a week with no data and says how many there are", () => {
    render(<SeriesChart label="Reach" unit="count" series={[week(7, 3), week(14, 4), week(21, null), week(28, 6)]} />);
    expect(screen.getAllByTestId("series-line")).toHaveLength(1);
    expect(screen.queryAllByTestId("series-dot")).toHaveLength(0); // the week on its own after the gap is the last point
    expect(screen.getByTestId("series-last")).toBeInTheDocument();
    expect(screen.getByTestId("series-gaps")).toHaveTextContent("1 week without data");
  });

  it("draws no line, and no last dot, when no week has a value", () => {
    render(<SeriesChart label="Reach" unit="count" series={[week(7, null), week(14, null)]} />);
    expect(screen.queryByTestId("series-line")).toBeNull();
    expect(screen.queryByTestId("series-last")).toBeNull();
    expect(screen.getByTestId("series-gaps")).toHaveTextContent("2 weeks without data");
  });

  it("reads a week with the week before it when focused and moved with the arrow keys", () => {
    render(<SeriesChart label="Messages received" unit="count" series={[week(7, 3), week(14, 5), week(21, 9)]} />);
    const plot = screen.getByTestId("line-plot");
    fireEvent.focus(plot);
    expect(screen.getByTestId("chart-tooltip")).toHaveTextContent("Week of 21 Sep");
    expect(screen.getByTestId("chart-tooltip")).toHaveTextContent("9");
    expect(screen.getByTestId("chart-tooltip")).toHaveTextContent("Week before: 5");
    fireEvent.keyDown(plot, { key: "ArrowLeft" });
    expect(screen.getByTestId("chart-tooltip")).toHaveTextContent("Week of 14 Sep");
    fireEvent.keyDown(plot, { key: "Escape" });
    expect(screen.queryByTestId("chart-tooltip")).toBeNull();
  });

  it("draws nothing for an empty series", () => {
    const { container } = render(<SeriesChart label="Reach" unit="count" series={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
