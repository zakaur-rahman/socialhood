import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinalCta } from "./FinalCta";

describe("the closing call to action (C-159 final CTA, C-161)", () => {
  it("claims Pro's trial only when one is passed, with one action and the email as a line", () => {
    const { container, rerender } = render(<FinalCta />);
    const section = container.querySelector("section.night.close") as HTMLElement;
    expect(section).toHaveAttribute("aria-labelledby", "cta-title");
    expect(screen.getByRole("heading", { level: 2 })).toHaveAttribute("id", "cta-title");
    expect(screen.getByRole("list", { name: "What you get" }).querySelectorAll("li")).toHaveLength(2);
    expect(screen.queryByText(/trial of Pro/)).toBeNull();
    expect(screen.getAllByRole("link").map((link) => link.textContent?.trim())).toEqual(["Start free", "support@amplychat.com"]);

    rerender(<FinalCta trialDays={14} />);
    expect(screen.getByText("14-day trial of Pro")).toBeInTheDocument();
  });

  it("opens on the channel line, a still, hidden picture with no loop and no image (C-161)", () => {
    const { container } = render(<FinalCta />);
    const line = container.querySelector(".close-in > .chan-line.close-line") as HTMLElement;
    expect(line).toHaveAttribute("aria-hidden");
    expect([...line.querySelectorAll<HTMLElement>("i")].map((part) => part.style.getPropertyValue("--c"))).toEqual(["var(--ig)", "var(--wa)", "var(--web)"]);
    expect(line.nextElementSibling).toBe(screen.getByRole("heading", { level: 2 }));
    // The lede on one side, the action, the facts and the email on the other.
    const row = container.querySelector(".close-row") as HTMLElement;
    expect(row.querySelector(".close-p")).not.toBeNull();
    expect(row.querySelector(".close-act .ctas a")).toHaveTextContent("Start free");
    expect(row.querySelector(".close-act .close-mail")).not.toBeNull();
    expect(container.querySelector(".converge")).toBeNull();
    expect(container.querySelector("[data-motion-scope]")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });
});
