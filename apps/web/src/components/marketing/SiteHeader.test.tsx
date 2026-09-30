import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ state: { isLoaded: true, isSignedIn: false as boolean | undefined } }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth.state }));

import { HeaderAuth } from "./HeaderAuth";
import { SiteHeader } from "./SiteHeader";

describe("the header's account actions", () => {
  beforeEach(() => {
    auth.state = { isLoaded: true, isSignedIn: false };
  });

  it("signed out: Sign in and Start free (Clerk's pages)", () => {
    render(<HeaderAuth />);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in");
    expect(screen.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "/sign-up");
    expect(screen.queryByRole("link", { name: "Open app" })).not.toBeInTheDocument();
  });

  it("signed in: Open app, to /app, instead", () => {
    auth.state = { isLoaded: true, isSignedIn: true };
    render(<HeaderAuth />);
    expect(screen.getByRole("link", { name: "Open app" })).toHaveAttribute("href", "/app");
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Start free" })).not.toBeInTheDocument();
  });

  it("while Clerk loads it shows what the static page shows: the signed-out actions", () => {
    auth.state = { isLoaded: false, isSignedIn: undefined };
    render(<HeaderAuth />);
    expect(screen.getByRole("link", { name: "Start free" })).toBeInTheDocument();
  });
});

describe("the site header", () => {
  beforeEach(() => {
    auth.state = { isLoaded: true, isSignedIn: false };
  });

  it("has the logo, the section links and the account actions", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Social Hood" })).toHaveAttribute("href", "/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(nav).toHaveTextContent("Features");
    for (const [name, href] of [
      ["Features", "/#features"],
      ["How it works", "/#how-it-works"],
      ["Pricing", "/#pricing"],
      ["FAQ", "/#faq"],
    ]) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
  });

  it("the phone menu opens and closes, and has the account actions", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    const toggle = screen.getByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    const panel = document.getElementById(toggle.getAttribute("aria-controls") as string) as HTMLElement;
    expect(panel).not.toBeVisible();

    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
    expect(panel).toBeVisible();
    expect(panel.querySelector('a[href="/sign-in"]')).not.toBeNull();

    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveFocus();
    expect(panel).not.toBeVisible();
  });

  it("the phone menu shows Open app to a signed-in visitor", async () => {
    auth.state = { isLoaded: true, isSignedIn: true };
    const user = userEvent.setup();
    render(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getAllByRole("link", { name: "Open app" }).length).toBe(2);
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  });
});
