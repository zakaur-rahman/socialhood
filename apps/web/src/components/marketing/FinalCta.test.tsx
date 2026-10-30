import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinalCta } from "./FinalCta";

describe("the closing call to action (C-159 final CTA)", () => {
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

  it("draws the channels converging as a still, hidden picture with no loop", () => {
    const { container } = render(<FinalCta />);
    const converge = container.querySelector(".converge") as HTMLElement;
    expect(converge).toHaveAttribute("aria-hidden");
    expect(converge.querySelectorAll("path.cv-line")).toHaveLength(4);
    converge.querySelectorAll("path.cv-line").forEach((path) => expect(path).toHaveAttribute("pathLength", "1"));
    expect(converge.querySelectorAll(".cv-mark")).toHaveLength(4);
    expect(converge.querySelector(".cv-hub [data-logo-mark]")).not.toBeNull();
    expect(container.querySelector("[data-motion-scope]")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });
});
