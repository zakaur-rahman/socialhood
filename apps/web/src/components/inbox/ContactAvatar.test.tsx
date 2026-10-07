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

  // UI-030: tokens, not palette or arbitrary values (DESIGN_SYSTEM §1.3, §2.2).
  it("the platform badge's glyph is on-brand; the 24 px initial is text-2xs", () => {
    const { container } = render(<ContactAvatar id="c1" name="priya" size={40} platform="instagram" />);
    const badge = container.querySelector('[data-platform="instagram"]');
    expect(badge).toHaveClass("text-on-brand", "bg-instagram");
    expect(badge).not.toHaveClass("text-white");
    render(<ContactAvatar id="c2" name="kabir" size={24} />);
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
