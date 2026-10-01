import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { METER_WARNING, Meter, meterLevel } from "./meter";

const slot = (name: string) => document.querySelector(`[data-slot="${name}"]`) as HTMLElement;

describe("meterLevel (UI-022)", () => {
  it("warns a consumable from 80% and marks it full at 100%, as billing's meters do today", () => {
    expect(METER_WARNING).toBe(0.8);
    expect(meterLevel(0, 500)).toBe("normal");
    expect(meterLevel(399, 500)).toBe("normal");
    expect(meterLevel(400, 500)).toBe("warning");
    expect(meterLevel(499, 500)).toBe("warning");
    expect(meterLevel(500, 500)).toBe("full");
    expect(meterLevel(650, 500)).toBe("full");
    expect(meterLevel(400, 500, "consumable")).toBe("warning");
  });

  it("never warns a slot, and marks it full only at 100%", () => {
    expect(meterLevel(4, 5, "slot")).toBe("normal");
    expect(meterLevel(5, 5, "slot")).toBe("full");
    expect(meterLevel(1, 1, "slot")).toBe("full");
    expect(meterLevel(3, 1, "slot")).toBe("full");
  });

  it("is normal without a limit", () => {
    expect(meterLevel(12_000, null)).toBe("normal");
    expect(meterLevel(12_000, undefined)).toBe("normal");
    expect(meterLevel(3, 0, "slot")).toBe("normal");
  });
});

describe("Meter (UI-022)", () => {
  it("is a role=meter named by its label, with the value text on screen and as aria-valuetext", () => {
    render(<Meter label="AI credits" value={412} max={500} unit="credits" />);
    const meter = screen.getByRole("meter", { name: "AI credits" });
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "500");
    expect(meter).toHaveAttribute("aria-valuenow", "412");
    expect(meter).toHaveAttribute("aria-valuetext", "412 of 500 credits");
    expect(screen.getByText("412 of 500 credits")).toBeVisible();
    expect(slot("meter")).toHaveAttribute("data-kind", "consumable");
  });

  it("draws a 6 px raised track with the decor-gradient fill at the share used", () => {
    render(<Meter label="Scheduled posts" value={30} max={100} unit="posts" />);
    const meter = screen.getByRole("meter", { name: "Scheduled posts" });
    expect(meter).toHaveClass("h-1.5", "rounded-full", "bg-raised", "overflow-hidden");
    const fill = slot("meter-fill");
    expect(fill).toHaveClass("bg-brand-gradient-decor", "rounded-full", "motion-reduce:transition-none");
    expect(fill).toHaveStyle({ width: "30%" });
    expect(slot("meter")).toHaveAttribute("data-level", "normal");
    expect(slot("meter-value")).toHaveClass("text-fg-secondary");
  });

  it("turns a consumable warning at 80% and danger at 100%, in the fill and the value text", () => {
    const { rerender } = render(<Meter label="AI credits" value={400} max={500} unit="credits" />);
    expect(slot("meter")).toHaveAttribute("data-level", "warning");
    expect(slot("meter-fill")).toHaveClass("bg-warning");
    expect(slot("meter-value")).toHaveClass("text-warning");

    rerender(
      <Meter
        label="AI credits"
        value={500}
        max={500}
        unit="credits"
        fullMessage="Your plan includes 500 credits a month."
        action={<a href="/billing">Upgrade</a>}
      />,
    );
    expect(slot("meter")).toHaveAttribute("data-level", "full");
    expect(slot("meter-fill")).toHaveClass("bg-danger");
    expect(slot("meter-fill")).toHaveStyle({ width: "100%" });
    expect(slot("meter-value")).toHaveClass("text-danger-fg");
    const meter = screen.getByRole("meter", { name: "AI credits" });
    expect(meter).toHaveAccessibleDescription("Your plan includes 500 credits a month. Upgrade");
    const message = screen.getByText("Your plan includes 500 credits a month.");
    expect(message).toHaveClass("text-danger-fg");
    expect(screen.queryByText("All used")).toBeNull();
  });

  it("keeps a full slot neutral and says All used, with its message and action", () => {
    render(
      <Meter
        label="Instagram accounts"
        kind="slot"
        value={1}
        max={1}
        unit="accounts"
        fullMessage="Free includes 1 account per platform."
        action={<a href="/billing">Upgrade</a>}
      />,
    );
    const root = slot("meter");
    expect(root).toHaveAttribute("data-kind", "slot");
    expect(root).toHaveAttribute("data-level", "full");
    expect(slot("meter-fill")).toHaveClass("bg-brand-gradient-decor");
    expect(slot("meter-fill")).not.toHaveClass("bg-danger");
    expect(slot("meter-value")).toHaveClass("text-fg-secondary");
    expect(screen.getByText("All used")).toBeVisible();
    expect(screen.getByText("Free includes 1 account per platform.").closest("p")).toHaveClass("text-fg-secondary");
    expect(screen.getByRole("meter", { name: "Instagram accounts" })).toHaveAccessibleDescription(
      "All used Free includes 1 account per platform. Upgrade",
    );
  });

  it("says All used for a full slot even without a message, and never warns it at 80%", () => {
    const { rerender } = render(<Meter label="Active automations" kind="slot" value={4} max={5} />);
    expect(slot("meter")).toHaveAttribute("data-level", "normal");
    expect(slot("meter-fill")).toHaveClass("bg-brand-gradient-decor");
    expect(screen.queryByText("All used")).toBeNull();
    rerender(<Meter label="Active automations" kind="slot" value={5} max={5} />);
    expect(screen.getByText("All used")).toBeVisible();
  });

  it("caps the bar and aria-valuenow at the limit, and keeps the real numbers in the text", () => {
    render(<Meter label="WhatsApp accounts" kind="slot" value={3} max={1} unit="accounts" />);
    const meter = screen.getByRole("meter", { name: "WhatsApp accounts" });
    expect(meter).toHaveAttribute("aria-valuenow", "1");
    expect(meter).toHaveAttribute("aria-valuetext", "3 of 1 accounts");
    expect(slot("meter-fill")).toHaveStyle({ width: "100%" });
  });

  it("formats numbers with grouping and takes a custom value text", () => {
    const { rerender } = render(<Meter label="Knowledge" value={120_500} max={200_000} unit="characters" />);
    expect(screen.getByText("120,500 of 200,000 characters")).toBeVisible();
    rerender(<Meter label="Lead score" value={72} max={100} valueText="72 / 100" />);
    expect(screen.getByRole("meter", { name: "Lead score" })).toHaveAttribute("aria-valuetext", "72 / 100");
    expect(screen.getByText("72 / 100")).toBeVisible();
  });

  it("has no bar and says no limit when there is no limit", () => {
    render(<Meter label="AI credits" value={12_000} max={null} unit="credits" />);
    expect(screen.queryByRole("meter")).toBeNull();
    expect(screen.getByText("12,000 credits · no limit")).toBeVisible();
    expect(slot("meter")).toHaveAttribute("data-level", "normal");
  });
});

describe("Meter ring (UI-022)", () => {
  it("is a compact role=meter that shows its percentage", () => {
    render(<Meter variant="ring" label="AI credits" value={312} max={500} unit="credits" />);
    const ring = screen.getByRole("meter", { name: "AI credits" });
    expect(ring).toHaveAttribute("data-variant", "ring");
    expect(ring).toHaveAttribute("aria-valuetext", "312 of 500 credits");
    expect(ring).toHaveClass("size-10");
    expect(ring).toHaveTextContent("62%");
    expect(ring.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(ring.querySelector("circle")).toHaveClass("stroke-raised");
    expect(slot("meter-fill")).toHaveClass("stroke-brand");
  });

  it("rounds down, so it reads 100% only when full, and shows <1% for a little use", () => {
    const { rerender } = render(<Meter variant="ring" label="AI credits" value={498} max={500} />);
    expect(screen.getByRole("meter")).toHaveTextContent("99%");
    expect(slot("meter-fill")).toHaveClass("stroke-warning");
    rerender(<Meter variant="ring" label="AI credits" value={500} max={500} />);
    expect(screen.getByRole("meter")).toHaveTextContent("100%");
    expect(slot("meter-fill")).toHaveClass("stroke-danger");
    rerender(<Meter variant="ring" label="AI credits" value={2} max={500} />);
    expect(screen.getByRole("meter")).toHaveTextContent("<1%");
    rerender(<Meter variant="ring" label="AI credits" value={0} max={500} />);
    expect(screen.getByRole("meter")).toHaveTextContent("0%");
    expect(slot("meter-fill")).toBeNull();
  });

  it("keeps a full slot's ring brand, and renders nothing without a limit", () => {
    const { rerender } = render(<Meter variant="ring" kind="slot" label="Accounts" value={2} max={2} />);
    expect(slot("meter-fill")).toHaveClass("stroke-brand");
    expect(screen.getByRole("meter")).toHaveTextContent("100%");
    rerender(<Meter variant="ring" label="AI credits" value={2} max={null} />);
    expect(screen.queryByRole("meter")).toBeNull();
    expect(slot("meter")).toBeNull();
  });
});
