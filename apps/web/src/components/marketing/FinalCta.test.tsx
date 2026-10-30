import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinalCta } from "./FinalCta";

describe("the closing call to action (C-159 final CTA, C-161 v2)", () => {
  it("claims Pro's trial only when one is passed, with two actions and no email", () => {
    const { container, rerender } = render(<FinalCta />);
    const section = container.querySelector("section.night.close") as HTMLElement;
    expect(section).toHaveAttribute("aria-labelledby", "cta-title");
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveAttribute("id", "cta-title");
    expect(heading).toHaveTextContent("Ready to take control of every conversation?");
    // The accent phrase, as the hero sets "One inbox.".
    expect(heading.querySelector("em")).toHaveTextContent("every conversation");
    const facts = screen.getByRole("list", { name: "What you get" });
    expect([...facts.querySelectorAll("li")].map((li) => li.textContent)).toEqual([
      "Free plan, no card required",
      "Official Meta APIs, no password needed",
    ]);
    expect(screen.queryByText(/Try Pro free/)).toBeNull();
    expect(screen.getAllByRole("link").map((link) => [link.textContent?.trim(), link.getAttribute("href")])).toEqual([
      ["Start free", "/sign-up"],
      ["See how it works", "/how-it-works"],
    ]);
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull();

    rerender(<FinalCta trialDays={14} />);
    expect(screen.getByText("Try Pro free for 14 days")).toBeInTheDocument();
  });

  it("puts a still, hidden arc behind the close: no channel line, no loop, no image (C-161 v2)", () => {
    const { container } = render(<FinalCta />);
    const arc = container.querySelector("section.close > .close-arc") as HTMLElement;
    expect(arc).toHaveAttribute("aria-hidden");
    expect(arc).toBeEmptyDOMElement();
    expect(container.querySelector(".close-line, .chan-line")).toBeNull();
    expect(container.querySelector(".converge")).toBeNull();
    expect(container.querySelector("[data-motion-scope]")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("never links the how-it-works page to itself: there the second action is every feature", () => {
    render(<FinalCta from="how-it-works" />);
    expect(screen.getByRole("link", { name: "See every feature" })).toHaveAttribute("href", "/features");
    expect(screen.queryByRole("link", { name: "See how it works" })).toBeNull();
  });
});
