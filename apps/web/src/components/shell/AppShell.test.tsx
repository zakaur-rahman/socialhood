import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ShellFrame } from "./AppShell";

function renderFrame() {
  return render(
    <ShellFrame
      topBar={<header>Top bar</header>}
      sidebar={
        <nav aria-label="Main">
          <button type="button">Home</button>
        </nav>
      }
    >
      <div data-testid="banner">Reconnect @maple</div>
      <button type="button">First control</button>
    </ShellFrame>,
  );
}

describe("ShellFrame (UI-006)", () => {
  it("the first Tab reaches Skip to content, which leads to <main>", async () => {
    const user = userEvent.setup();
    renderFrame();
    await user.tab();
    const skip = screen.getByRole("link", { name: "Skip to content" });
    expect(skip).toHaveFocus();
    expect(skip).toHaveAttribute("href", "#main");
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main");
    // Focusable as the link's target, but not a Tab stop of its own.
    expect(main).toHaveAttribute("tabindex", "-1");
    await user.tab();
    expect(screen.getByRole("button", { name: "Home" })).toHaveFocus();
  });

  it("no complementary landmark around the nav; banners are in <main>'s flow; unsized text is 14 px", () => {
    renderFrame();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(main.firstElementChild).toBe(screen.getByTestId("banner"));
    expect(main).toHaveClass("text-sm");
  });
});
