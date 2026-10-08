import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkspaceError from "./error";

const nav = vi.hoisted(() => ({ pathname: "/w/maple/knowledge" }));
vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "maple" }),
  usePathname: () => nav.pathname,
}));

describe("the workspace error boundary (UX-011, UI-ISS-068)", () => {
  beforeEach(() => {
    nav.pathname = "/w/maple/knowledge";
  });

  it("says the page didn't load, without the raw error, and Try again retries the page", async () => {
    const retry = vi.fn();
    render(<WorkspaceError error={new TypeError("Cannot read properties of undefined (reading 'map')")} retry={retry} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("This didn't load");
    expect(alert).toHaveTextContent("Something went wrong on our side. Try again.");
    expect(alert).not.toHaveTextContent("Cannot read properties");
    // It fills the rest of <main> below the banners, so the shell around it stays as it was.
    expect(alert).toHaveClass("flex-1");
    expect(alert).not.toHaveClass("min-h-dvh");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("offers Go to Home, to the workspace's Home", () => {
    render(<WorkspaceError error={new Error("boom")} retry={() => {}} />);
    expect(screen.getByRole("link", { name: "Go to Home" })).toHaveAttribute("href", "/w/maple/home");
  });

  it("doesn't offer Go to Home on Home itself", () => {
    nav.pathname = "/w/maple/home";
    render(<WorkspaceError error={new Error("boom")} retry={() => {}} />);
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Go to Home" })).toBeNull();
  });
});
