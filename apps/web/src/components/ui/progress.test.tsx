import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Progress } from "./progress";

const fill = () => document.querySelector('[data-slot="progress-fill"]') as HTMLElement;

describe("Progress (UI-022)", () => {
  it("is a named role=progressbar out of 100 by default", () => {
    render(<Progress aria-label="Uploading photo.jpg" value={40} />);
    const bar = screen.getByRole("progressbar", { name: "Uploading photo.jpg" });
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveAttribute("aria-valuenow", "40");
    expect(bar).not.toHaveAttribute("aria-valuetext");
    expect(fill()).toHaveStyle({ width: "40%" });
  });

  it("takes a total and a value text, and a name from visible text", () => {
    render(
      <>
        <p id="analysis-status">Analysing 12,400 of 58,000 comments</p>
        <Progress aria-labelledby="analysis-status" value={12_400} max={58_000} valueText="12,400 of 58,000 comments" />
      </>,
    );
    const bar = screen.getByRole("progressbar", { name: "Analysing 12,400 of 58,000 comments" });
    expect(bar).toHaveAttribute("aria-valuemax", "58000");
    expect(bar).toHaveAttribute("aria-valuenow", "12400");
    expect(bar).toHaveAttribute("aria-valuetext", "12,400 of 58,000 comments");
    expect(fill().style.width).toMatch(/^21\.37/);
  });

  it("shares Meter's 6 px raised track and decor fill, with no thresholds, and stops moving under reduced motion", () => {
    render(<Progress aria-label="Uploading" value={100} />);
    expect(screen.getByRole("progressbar")).toHaveClass("h-1.5", "w-full", "rounded-full", "bg-raised", "overflow-hidden");
    expect(fill()).toHaveClass(
      "bg-brand-gradient-decor",
      "rounded-full",
      "transition-[width]",
      "duration-normal",
      "motion-reduce:transition-none",
    );
    expect(fill()).not.toHaveClass("bg-danger");
    expect(fill()).toHaveStyle({ width: "100%" });
  });

  it("clamps its value to the range", () => {
    const { rerender } = render(<Progress aria-label="Uploading" value={140} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    expect(fill()).toHaveStyle({ width: "100%" });
    rerender(<Progress aria-label="Uploading" value={-5} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    expect(fill()).toHaveStyle({ width: "0%" });
  });
});
