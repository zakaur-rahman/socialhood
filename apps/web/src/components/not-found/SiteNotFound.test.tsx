import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SiteNotFound } from "./SiteNotFound";

vi.mock("next/navigation", () => ({ usePathname: () => "/nope" }));

describe("SiteNotFound (C-159)", () => {
  it("says what happened, shows the path, keeps the ways out and links the main pages", () => {
    render(
      <SiteNotFound>
        <a href="/pricing">See pricing</a>
      </SiteNotFound>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "We can't find that page" })).toBeInTheDocument();
    expect(screen.getByTestId("requested-path")).toHaveTextContent("/nope");
    expect(screen.getByRole("link", { name: "See pricing" })).toBeInTheDocument();
    const places = within(screen.getByRole("navigation", { name: "Popular pages" })).getAllByRole("link");
    expect(places.map((link) => link.textContent)).toEqual([
      "Features",
      "How it works",
      "Guides",
      "Common questions",
      "What's new",
      "Contact",
    ]);
    expect(screen.getByRole("link", { name: "Common questions" })).toHaveAttribute("href", "/faq");
  });
});
