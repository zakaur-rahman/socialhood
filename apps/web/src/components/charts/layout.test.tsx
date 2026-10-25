import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BarChart } from "./BarChart";
import { ChartTable } from "./ChartTable";
import { LineChart } from "./LineChart";

const css = readFileSync(join(__dirname, "..", "..", "styles", "globals.css"), "utf8");

describe("the colour order", () => {
  it("opens with the colours that differ most: indigo, orange, aqua, yellow, magenta, then blue", () => {
    const hue = (n: number) => css.match(new RegExp(`--color-chart-series-${n}:\\s*light-dark\\((#[0-9A-F]{6}),`, "i"))?.[1].toUpperCase();
    // Series 1 is the brand indigo (an alias); the rest are written out in the order they are given out.
    expect(css).toMatch(/--color-chart-series-1:\s*var\(--color-brand\)/);
    expect([2, 3, 4, 5, 6].map(hue)).toEqual(["#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#2A8FD8"]);
  });
});

describe("what keeps a chart inside its container", () => {
  it("clips the screen-reader table in a box, so a wide table cannot widen the page", () => {
    render(<ChartTable caption="Messages" columns={["Week", "A very long account name that would be wide"]} rows={[{ key: "1", cells: ["Week of 1 Sep", "12"] }]} />);
    const table = screen.getByTestId("chart-table");
    expect(table.parentElement).toHaveClass("sr-only");
    expect(table).not.toHaveClass("sr-only");
  });

  it("keeps a duration axis label on one line in a gutter as wide as the longest label", () => {
    render(
      <LineChart
        label="Median first response"
        points={[
          { key: "a", label: "1 Sep" },
          { key: "b", label: "8 Sep" },
        ]}
        series={[{ key: "s", label: "Median", color: 0, values: [3600, 28 * 3600] }]}
        format={(v) => `${v} s`}
        tickFormat={(v) => `${Math.round(v / 3600)}h`}
      />,
    );
    const gutter = screen.getByTestId("line-chart").querySelector("[aria-hidden].relative") as HTMLElement;
    expect(gutter).toHaveClass("whitespace-nowrap");
    expect(Number.parseInt(gutter.style.width, 10)).toBeGreaterThanOrEqual(4);
  });

  it("leaves room above the chart for the top axis label", () => {
    render(<LineChart label="L" points={[{ key: "a", label: "1" }, { key: "b", label: "2" }]} series={[{ key: "s", label: "S", color: 0, values: [1, 2] }]} format={String} />);
    expect(screen.getByTestId("line-plot").parentElement?.parentElement).toHaveClass("pt-2");
  });
});

describe("points and bars that are not there", () => {
  it("does not draw a lone dot before a line that starts mid-chart, and a single reading is a dot", () => {
    const points = ["1", "2", "3", "4"].map((label) => ({ key: label, label }));
    const { rerender } = render(<LineChart label="L" points={points} series={[{ key: "s", label: "S", color: 0, values: [5, null, null, 7] }]} format={String} />);
    expect(screen.queryAllByTestId("series-dot")).toHaveLength(0);
    expect(screen.getAllByTestId("series-last")).toHaveLength(1);
    rerender(<LineChart label="L" points={points} series={[{ key: "s", label: "S", color: 0, values: [null, null, 6, null] }]} format={String} />);
    expect(screen.getAllByTestId("series-last")).toHaveLength(1);
  });

  it("draws an empty track for a zero, never a stray line", () => {
    render(<BarChart label="B" rows={[{ key: "a", name: "A", label: "A", color: 0, value: 0, previous: 0 }, { key: "b", name: "B", label: "B", color: 1, value: 3, previous: 1 }]} format={String} />);
    expect(screen.getAllByTestId("bar-current")).toHaveLength(1);
    expect(document.querySelector("[data-row=a]")?.querySelector(".border-l")).toBeNull();
  });
});
