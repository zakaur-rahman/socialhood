import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NotFoundIllustration } from "./NotFoundIllustration";
import { NotFoundPage } from "./NotFoundPage";

vi.mock("next/navigation", () => ({ usePathname: () => "/w/maple/nope" }));

describe("NotFoundPage", () => {
  it("says what happened, shows the requested path and the ways out", () => {
    render(
      <NotFoundPage>
        <span role="link">Go home</span>
      </NotFoundPage>,
    );
    expect(screen.getByRole("heading", { name: "We can't find that page" })).toBeInTheDocument();
    expect(screen.getByTestId("requested-path")).toHaveTextContent("/w/maple/nope");
    expect(screen.getByRole("link", { name: "Go home" })).toBeInTheDocument();
  });
});

describe("NotFoundIllustration", () => {
  it("is decorative and built from tokens only", () => {
    render(<NotFoundIllustration />);
    const svg = screen.getByTestId("not-found-illustration");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg.innerHTML).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(/i);
  });
});
