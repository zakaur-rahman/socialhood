import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { avatarGradient } from "@/lib/inbox/format";

import { ContactAvatar } from "./ContactAvatar";

describe("ContactAvatar", () => {
  it("draws the initial on the contact's identity gradient in on-brand (D-13)", () => {
    render(<ContactAvatar id="c1" name="priya" size={40} />);
    const initial = screen.getByText("P");
    const [from, to] = avatarGradient("c1").split(" ");
    expect(initial).toHaveClass("bg-linear-135", from, to, "text-on-brand", "font-semibold", "text-base");
    expect(initial).toHaveAttribute("data-gradient", avatarGradient("c1"));
    expect(initial).not.toHaveClass("text-white");
  });

  // UI-031: the Avatar primitive's sizes, with its AvatarBadge in the platform's fill (UI-016).
  it.each([
    [48, "lg"],
    [40, "lg"],
    [32, "default"],
    [24, "sm"],
  ] as const)("%i px is the Avatar's %s size", (size, avatarSize) => {
    render(<ContactAvatar id="c1" name="priya" size={size} />);
    expect(screen.getByTestId("contact-avatar")).toHaveAttribute("data-size", avatarSize);
  });

  it("48 px is lg drawn at 48 px, replacing lg's 40 px on the same variant", () => {
    render(<ContactAvatar id="c1" name="priya" size={48} />);
    const avatar = screen.getByTestId("contact-avatar");
    expect(avatar).toHaveClass("data-[size=lg]:size-12");
    expect(avatar).not.toHaveClass("data-[size=lg]:size-10");
  });

  it("the platform badge is AvatarBadge: the platform's fill, an on-brand glyph, cut out by a panel ring", () => {
    const { container } = render(<ContactAvatar id="c1" name="priya" size={40} platform="instagram" />);
    const badge = container.querySelector('[data-platform="instagram"]');
    expect(badge).toHaveAttribute("data-slot", "avatar-badge");
    expect(badge).toHaveClass("text-on-brand", "bg-instagram", "ring-2", "ring-panel");
    expect(badge).not.toHaveClass("bg-primary", "text-white");
    expect(badge?.querySelector("svg")).not.toBeNull();
  });

  it("the 24 px avatar has no badge; its initial is text-2xs", () => {
    const { container } = render(<ContactAvatar id="c2" name="kabir" size={24} platform="whatsapp" />);
    expect(container.querySelector("[data-platform]")).toBeNull();
    expect(screen.getByText("K")).toHaveClass("text-2xs");
  });

  it("hides the initial from screen readers: the name sits beside every avatar", () => {
    render(
      <a href="/c1">
        <ContactAvatar id="c1" name="Priya" />
        Priya
      </a>,
    );
    expect(screen.getByText("P")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("link")).toHaveAccessibleName("Priya");
  });
});
