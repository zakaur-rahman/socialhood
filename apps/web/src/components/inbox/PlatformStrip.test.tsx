import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PlatformStrip } from "./PlatformStrip";

describe("PlatformStrip (UX-INB-02)", () => {
  it("All + 1 platform: two segments", () => {
    render(<PlatformStrip platforms={["instagram"]} value="all" onChange={() => {}} showLabels />);
    const group = screen.getByRole("group", { name: "Platform" });
    expect(group).toHaveClass("grid-cols-2");
    expect(screen.getAllByRole("button")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  });

  it("All + 2 platforms: three segments", () => {
    render(<PlatformStrip platforms={["instagram", "whatsapp"]} value="all" onChange={() => {}} showLabels />);
    expect(screen.getByRole("group", { name: "Platform" })).toHaveClass("grid-cols-3");
    expect(screen.getByRole("button", { name: "WhatsApp" })).toBeInTheDocument();
  });

  it("takes the active segment's colour", () => {
    const { rerender } = render(<PlatformStrip platforms={["instagram", "whatsapp"]} value="all" onChange={() => {}} showLabels />);
    expect(screen.getByRole("group")).toHaveClass("bg-brand-gradient");
    rerender(<PlatformStrip platforms={["instagram", "whatsapp"]} value="instagram" onChange={() => {}} showLabels />);
    expect(screen.getByRole("group")).toHaveClass("bg-instagram");
    expect(screen.getByRole("button", { name: "Instagram" })).toHaveClass("bg-instagram", "border-white/40");
    expect(screen.getByRole("button", { name: "WhatsApp" })).toHaveClass("bg-panel", "border-transparent");
    rerender(<PlatformStrip platforms={["instagram", "whatsapp"]} value="whatsapp" onChange={() => {}} showLabels />);
    expect(screen.getByRole("group")).toHaveClass("bg-whatsapp");
  });

  it("hides labels below 1280 px but keeps accessible names", async () => {
    const onChange = vi.fn();
    render(<PlatformStrip platforms={["instagram"]} value="all" onChange={onChange} showLabels={false} />);
    const button = screen.getByRole("button", { name: "Instagram" });
    expect(button).toHaveTextContent("");
    await userEvent.click(button);
    expect(onChange).toHaveBeenCalledWith("instagram");
  });

  it("shows a skeleton while accounts load", () => {
    render(<PlatformStrip platforms={[]} value="all" onChange={() => {}} showLabels loading />);
    expect(screen.getByLabelText("Loading platforms")).toHaveAttribute("aria-busy", "true");
  });
});
