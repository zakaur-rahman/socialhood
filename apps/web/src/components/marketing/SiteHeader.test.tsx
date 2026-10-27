import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ state: { isLoaded: true, isSignedIn: false as boolean | undefined } }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth.state }));

import { ClerkSignedIn } from "@/components/auth/ClerkSignedIn";
import { SignedInHint } from "@/components/auth/signed-in";

import { HeaderAuth } from "./HeaderAuth";
import { SiteHeader } from "./SiteHeader";

/** With one origin the root layout puts every page under Clerk (ClerkSignedIn). */
const withClerk = (ui: React.ReactElement) => render(<ClerkSignedIn>{ui}</ClerkSignedIn>);

describe("the header's account actions", () => {
  beforeEach(() => {
    auth.state = { isLoaded: true, isSignedIn: false };
  });

  it("signed out: Sign in and Start free (Clerk's pages)", () => {
    withClerk(<HeaderAuth />);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in");
    expect(screen.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "/sign-up");
    expect(screen.queryByRole("link", { name: "Open app" })).not.toBeInTheDocument();
  });

  it("signed in: Open app, to /app, instead", () => {
    auth.state = { isLoaded: true, isSignedIn: true };
    withClerk(<HeaderAuth />);
    expect(screen.getByRole("link", { name: "Open app" })).toHaveAttribute("href", "/app");
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Start free" })).not.toBeInTheDocument();
  });

  it("links straight to the app's own host when it has one (C-146)", () => {
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://dashboard.amplychat.com");
    try {
      withClerk(<HeaderAuth />);
      expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "https://dashboard.amplychat.com/sign-in");
      expect(screen.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "https://dashboard.amplychat.com/sign-up");
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it("while Clerk loads it shows what the static page shows: the signed-out actions", () => {
    auth.state = { isLoaded: false, isSignedIn: undefined };
    withClerk(<HeaderAuth />);
    expect(screen.getByRole("link", { name: "Start free" })).toBeInTheDocument();
  });
});

describe("the site header", () => {
  beforeEach(() => {
    auth.state = { isLoaded: true, isSignedIn: false };
  });

  it("has the logo, the section links and the account actions", () => {
    withClerk(<SiteHeader />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Amplychat" })).toHaveAttribute("href", "/");
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
    withClerk(<SiteHeader />);
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
    withClerk(<SiteHeader />);
    await user.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getAllByRole("link", { name: "Open app" }).length).toBe(2);
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  });
});

describe("the header with the app on its own host (C-148): no Clerk, the cookie hint", () => {
  afterEach(() => {
    document.cookie = "__client_uat=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("signed out without Clerk's cookie", () => {
    render(
      <SignedInHint>
        <HeaderAuth />
      </SignedInHint>,
    );
    expect(screen.getByRole("link", { name: "Start free" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open app" })).not.toBeInTheDocument();
  });

  it("Open app once the cookie says a session exists", () => {
    document.cookie = "__client_uat=1761550000";
    render(
      <SignedInHint>
        <HeaderAuth />
      </SignedInHint>,
    );
    expect(screen.getByRole("link", { name: "Open app" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  });
});
