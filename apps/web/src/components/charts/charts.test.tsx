import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BarChart } from "./BarChart";
import { ChartLegend } from "./ChartLegend";
import { LineChart, labelIndexes } from "./LineChart";
import { colourIndexes, MAX_SERIES, seriesStyle } from "./palette";
import { Sparkline } from "./Sparkline";

const points = ["1 Sep", "8 Sep", "15 Sep"].map((label, i) => ({ key: `k${i}`, label, title: `Week of ${label}` }));
const count = (n: number) => String(n);

describe("the palette", () => {
  it("has six hues of its own in a fixed order and a neutral for the rest", () => {
    expect(MAX_SERIES).toBe(6);
    expect(seriesStyle(0).bg).toBe("bg-chart-series-1");
    expect(seriesStyle(5).line).toBe("stroke-chart-series-6");
    expect(seriesStyle(6).bg).toBe("bg-chart-neutral");
  });

  it("colours an entity by its place in a stable list", () => {
    const indexes = colourIndexes(["a", "b", "c"]);
    expect(indexes.get("c")).toBe(2);
  });
});

describe("LineChart", () => {
  const series = [
    { key: "a", label: "Maple", color: 0, values: [1, 4, 6] },
    { key: "b", label: "Chai", color: 1, values: [2, null, 3] },
  ];

  it("draws a line per series in its colour, a legend, and the numbers in a table", () => {
    render(<LineChart label="Messages" points={points} series={series} format={count} />);
    // The second series is two single points either side of a gap: dots, no line.
    expect(screen.getAllByTestId("series-line")).toHaveLength(1);
    expect(screen.getAllByTestId("series-line")[0]).toHaveClass("stroke-chart-series-1");
    expect(within(screen.getByTestId("chart-legend")).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Maple", "Chai"]);
    const table = screen.getByRole("table", { name: "Messages" });
    expect(within(table).getAllByRole("row").map((row) => row.textContent)).toEqual(["WeekMapleChai", "Week of 1 Sep12", "Week of 8 Sep4No data", "Week of 15 Sep63"]);
  });

  it("shows every series at the hovered week, and the keyboard moves between weeks", () => {
    render(<LineChart label="Messages" points={points} series={series} format={count} beforeLabel="Week before" />);
    const plot = screen.getByTestId("line-plot");
    // jsdom has no layout, so the pointer reads as the far right: the last week.
    fireEvent.pointerMove(plot, { clientX: 0 });
    const tip = screen.getByTestId("chart-tooltip");
    expect(tip).toHaveTextContent("Week of 15 Sep");
    expect(tip).toHaveTextContent("Maple");
    expect(tip).toHaveTextContent("Chai");
    fireEvent.keyDown(plot, { key: "ArrowLeft" });
    expect(screen.getByTestId("chart-tooltip")).toHaveTextContent("No data");
    fireEvent.keyDown(plot, { key: "Home" });
    expect(screen.getByTestId("chart-tooltip")).toHaveTextContent("Week of 1 Sep");
    fireEvent.pointerLeave(plot);
    expect(screen.queryByTestId("chart-tooltip")).toBeNull();
  });

  it("scales a share from 0 to 100 when pinned", () => {
    render(<LineChart label="Rate" points={points} series={[{ key: "a", label: "Rate", color: 0, values: [10, 20, 30] }]} format={(n) => `${n}%`} fixedTop={100} />);
    expect(screen.getAllByText("100%").length).toBeGreaterThan(0);
  });

  it("needs no legend for one series", () => {
    render(<LineChart label="Messages" points={points} series={[series[0]]} format={count} />);
    expect(screen.queryByTestId("chart-legend")).toBeNull();
  });

  it("prints a few x labels, never so many they collide", () => {
    expect(labelIndexes(3)).toEqual([0, 1, 2]);
    expect(labelIndexes(8)).toEqual([0, 2, 4, 5, 7]);
  });
});

describe("BarChart", () => {
  const rows = [
    { key: "a", name: "Maple", label: "Maple", color: 0, value: 90, previous: 60 },
    { key: "b", name: "Chai", label: "Chai", color: 1, value: 45, previous: 60 },
    { key: "c", name: "Fizz", label: "Fizz", color: 2, value: null, unavailable: "Not available" },
  ];

  it("draws this period in the entity's colour and the one before lighter, on one scale", () => {
    render(<BarChart label="Messages" rows={rows} format={count} />);
    const [first, second] = screen.getAllByTestId("bar-current");
    expect(first).toHaveClass("bg-chart-series-1");
    expect(second).toHaveClass("bg-chart-series-2");
    expect(first).toHaveStyle({ width: "100%" });
    expect(second).toHaveStyle({ width: "50%" });
    expect(screen.getAllByTestId("bar-previous")[0]).toHaveClass("opacity-40");
  });

  it("says why a row has no bar instead of drawing 0", () => {
    render(<BarChart label="Messages" rows={rows} format={count} />);
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("bar-current")).toHaveLength(2);
  });

  it("reads both values and the change on focus", () => {
    render(<BarChart label="Messages" rows={rows} format={count} change={(row) => (row.key === "a" ? "+50%" : null)} />);
    const row = document.querySelector("[data-row=a]") as HTMLElement;
    fireEvent.focus(row);
    const tip = screen.getByTestId("chart-tooltip");
    expect(tip).toHaveTextContent("This week");
    expect(tip).toHaveTextContent("90");
    expect(tip).toHaveTextContent("Last week");
    expect(tip).toHaveTextContent("+50%");
    fireEvent.blur(row);
    expect(screen.queryByTestId("chart-tooltip")).toBeNull();
  });
});

describe("ChartLegend and Sparkline", () => {
  it("is for two or more series", () => {
    const { container } = render(<ChartLegend items={[{ key: "a", label: "A", color: 0 }]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("draws a sparkline in the entity's colour, labelled only when given a label", () => {
    const { container, rerender } = render(<Sparkline values={[1, 3, null, 5]} color={3} />);
    expect(container.querySelector("polyline")).toHaveClass("stroke-chart-series-4");
    expect(screen.queryByRole("img")).toBeNull();
    rerender(<Sparkline values={[1, 3]} label="Runs: 1, 3" />);
    expect(screen.getByRole("img", { name: "Runs: 1, 3" })).toBeInTheDocument();
  });

  it("draws nothing for a series with no values", () => {
    const { container } = render(<Sparkline values={[null, null]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
