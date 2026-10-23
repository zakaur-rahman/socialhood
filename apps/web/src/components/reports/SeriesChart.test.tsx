import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SeriesChart } from "./SeriesChart";

const week = (day: number, value: number | null) => ({ week_start: `2026-09-${String(day).padStart(2, "0")}`, value });

describe("SeriesChart (GR-34)", () => {
  it("draws one line in the series colour and a dot on the latest week", () => {
    render(<SeriesChart label="Messages received" unit="count" series={[week(7, 3), week(14, 5), week(21, 9)]} />);
    expect(screen.getAllByTestId("series-line")).toHaveLength(1);
    expect(screen.getByTestId("series-last")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveClass("text-chart-series-1");
    expect(screen.queryByTestId("series-gaps")).toBeNull();
    // The first and last week sit under it as text.
    expect(screen.getByText("7 Sep")).toBeInTheDocument();
    expect(screen.getByText("21 Sep")).toBeInTheDocument();
  });

  it("labels the picture with every week in words, gaps included", () => {
    render(<SeriesChart label="Reach" unit="count" series={[week(7, 12), week(14, null), week(21, 20)]} />);
    expect(screen.getByRole("img", { name: "Reach, 3 weeks from 7 Sep: 12, no data, 20" })).toBeInTheDocument();
  });

  it("breaks the line at a week with no data and says how many there are", () => {
    render(<SeriesChart label="Reach" unit="count" series={[week(7, 3), week(14, 4), week(21, null), week(28, 6)]} />);
    expect(screen.getAllByTestId("series-line")).toHaveLength(1);
    expect(screen.getAllByTestId("series-dot")).toHaveLength(1); // the week on its own after the gap
    expect(screen.getByTestId("series-gaps")).toHaveTextContent("1 week without data");
  });

  it("draws no line, and no last dot, when no week has a value", () => {
    render(<SeriesChart label="Reach" unit="count" series={[week(7, null), week(14, null)]} />);
    expect(screen.queryByTestId("series-line")).toBeNull();
    expect(screen.queryByTestId("series-last")).toBeNull();
    expect(screen.getByTestId("series-gaps")).toHaveTextContent("2 weeks without data");
  });

  it("draws nothing for an empty series", () => {
    const { container } = render(<SeriesChart label="Reach" unit="count" series={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
