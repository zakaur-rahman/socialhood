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
