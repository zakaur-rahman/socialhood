import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PlatformStrip } from "./PlatformStrip";

describe("PlatformStrip, the segmented platform control (UX-INB-02, C-063)", () => {
  // UI-030: the strip is the ToggleGroup primitive, so the segments share the track equally
  // (`flex-1` items) instead of a grid with one column per choice.
  it("All + 1 platform: two segments", () => {
    render(<PlatformStrip platforms={["instagram"]} value="all" onChange={() => {}} />);
    const group = screen.getByRole("radiogroup", { name: "Platform" });
    expect(group).toHaveAttribute("data-slot", "toggle-group");
    expect(group).toHaveAttribute("data-variant", "segmented");
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    expect(screen.getByRole("radio", { name: "All" })).toHaveAttribute("aria-checked", "true");
  });

  it("All + 2 platforms: three segments, the small size", () => {
    render(<PlatformStrip platforms={["instagram", "whatsapp"]} value="all" onChange={() => {}} />);
    const group = screen.getByRole("radiogroup", { name: "Platform" });
    expect(group).toHaveAttribute("data-size", "sm");
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    for (const segment of screen.getAllByRole("radio")) expect(segment).toHaveClass("flex-1");
    expect(screen.getByRole("radio", { name: "WhatsApp" })).toBeInTheDocument();
  });

  // D-15 item 1 (C-069): the chosen segment is neutral, raised with brand-fg text, like every other
  // segmented control; no longer the brand-strong fill UI-002 gave it.
  it("the chosen segment is the neutral one; the others stay on the track", () => {
    const { rerender } = render(<PlatformStrip platforms={["instagram", "whatsapp"]} value="all" onChange={() => {}} />);
    const all = screen.getByRole("radio", { name: "All" });
    expect(all).toHaveAttribute("data-state", "on");
    expect(all).toHaveClass("data-[state=on]:bg-raised", "data-[state=on]:text-brand-fg");
    expect(all).not.toHaveClass("bg-brand-strong");
    rerender(<PlatformStrip platforms={["instagram", "whatsapp"]} value="instagram" onChange={() => {}} />);
    expect(screen.getByRole("radiogroup")).toHaveAttribute("data-active", "instagram");
    expect(screen.getByRole("radio", { name: "Instagram" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Instagram" })).toHaveAttribute("data-state", "on");
    expect(screen.getByRole("radio", { name: "WhatsApp" })).toHaveAttribute("data-state", "off");
  });

  it("labels every segment and reports the choice", async () => {
    const onChange = vi.fn();
    render(<PlatformStrip platforms={["instagram"]} value="all" onChange={onChange} />);
    const segment = screen.getByRole("radio", { name: "Instagram" });
    expect(segment).toHaveTextContent("Instagram");
    await userEvent.click(segment);
    expect(onChange).toHaveBeenCalledWith("instagram");
  });

  it("choosing the chosen segment again changes nothing", async () => {
    const onChange = vi.fn();
    render(<PlatformStrip platforms={["instagram"]} value="all" onChange={onChange} />);
    await userEvent.click(screen.getByRole("radio", { name: "All" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows a skeleton while accounts load", () => {
    render(<PlatformStrip platforms={[]} value="all" onChange={() => {}} loading />);
    expect(screen.getByLabelText("Loading platforms")).toHaveAttribute("aria-busy", "true");
  });
});
