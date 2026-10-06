import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Route } from "next";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { greeting } from "@/lib/copy";

import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";

const HOME = "/w/maple/home" as Route;

const internal = new ApiError({
  type: "t",
  title: "Something went wrong",
  status: 500,
  code: "internal",
  request_id: "01M3REQUESTID",
});

describe("ErrorState (§4.7)", () => {
  it("gives the internal message with the request id and a Retry", async () => {
    const retry = vi.fn();
    render(<ErrorState error={internal} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Something went wrong on our side. Try again. If it keeps happening, email support@socialhood.com with code 01M3REQUESTID.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("uses the offline message for network failures", () => {
    const offline = new ApiError({ type: "about:blank", title: "Request failed", status: 0, code: "network" });
    render(<ErrorState error={offline} />);
    expect(screen.getByRole("alert")).toHaveTextContent("You're offline. Reconnect and try again.");
  });
});

describe("ErrorState: buttons and sizes (UI-025)", () => {
  it("is centred by default, with Try again at the default size: 32 px, 40 px on coarse pointers", () => {
    render(<ErrorState error={internal} onRetry={() => {}} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("data-size", "default");
    expect(alert).toHaveClass("items-center", "text-center", "py-10");
    const retry = screen.getByRole("button", { name: "Try again" });
    expect(retry).toHaveAttribute("data-variant", "secondary");
    expect(retry).toHaveAttribute("data-size", "default");
    expect(retry).toHaveClass("h-8", "pointer-coarse:min-h-10");
    expect(screen.queryByRole("link", { name: "Go to Home" })).toBeNull();
  });

  it("offers Go to Home beside Try again when given the way home", async () => {
    const retry = vi.fn();
    render(<ErrorState error={internal} onRetry={retry} homeHref={HOME} />);
    const home = screen.getByRole("link", { name: "Go to Home" });
    expect(home).toHaveAttribute("href", "/w/maple/home");
    expect(home).toHaveAttribute("data-variant", "ghost");
    expect(home).toHaveClass("h-8", "pointer-coarse:min-h-10");
    // Same row, Try again first.
    const retryButton = screen.getByRole("button", { name: "Try again" });
    expect(retryButton.parentElement).toBe(home.parentElement);
    expect(retryButton.compareDocumentPosition(home) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await userEvent.click(retryButton);
    expect(retry).toHaveBeenCalledOnce();
  });

  it("compact: left-aligned 14 px text and small buttons, still 40 px on coarse pointers", () => {
    render(<ErrorState size="compact" error={internal} onRetry={() => {}} homeHref={HOME} className="mt-2" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("data-size", "compact");
    expect(alert).toHaveClass("text-left", "text-sm", "items-start", "mt-2");
    expect(alert).not.toHaveClass("text-center", "py-10");
    expect(alert).toHaveTextContent("This didn't load");
    expect(alert).toHaveTextContent("email support@socialhood.com with code 01M3REQUESTID");
    for (const control of [screen.getByRole("button", { name: "Try again" }), screen.getByRole("link", { name: "Go to Home" })]) {
      expect(control).toHaveAttribute("data-size", "sm");
      expect(control).toHaveClass("h-7", "pointer-coarse:min-h-10");
    }
  });

  it("fills the viewport only when asked", () => {
    render(<ErrorState fullPage error={internal} />);
    expect(screen.getByRole("alert")).toHaveClass("min-h-dvh");
  });
});

describe("EmptyState", () => {
  it("renders title, body and action", () => {
    render(<EmptyState title="No notifications" body="We'll tell you." action={<button>Act</button>} />);
    expect(screen.getByText("No notifications")).toBeInTheDocument();
    expect(screen.getByText("We'll tell you.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
  });

  it("is centred by default, with a 16 px title", () => {
    render(<EmptyState title="No drafts" body="Posts you start wait here." />);
    const state = screen.getByText("No drafts").parentElement!;
    expect(state).toHaveAttribute("data-size", "default");
    expect(state).toHaveClass("items-center", "text-center", "py-10");
    expect(screen.getByText("No drafts")).toHaveClass("text-base", "font-semibold");
  });

  it("compact: left-aligned 14 px text, a 14 px semibold title and secondary body", () => {
    render(
      <EmptyState
        size="compact"
        icon={<svg data-testid="icon" className="size-8" />}
        title="No drafts"
        body="Posts you start wait here."
        action={<button>New post</button>}
        className="p-4"
      />,
    );
    const title = screen.getByText("No drafts");
    const state = title.closest("[data-size]")!;
    expect(state).toHaveAttribute("data-size", "compact");
    expect(state).toHaveClass("text-left", "text-sm", "items-start", "p-4");
    expect(state).not.toHaveClass("text-center", "py-10");
    expect(title).toHaveClass("font-semibold");
    expect(title).not.toHaveClass("text-base");
    expect(screen.getByText("Posts you start wait here.")).toHaveClass("text-fg-secondary");
    // The icon shrinks to the 14 px line (16 px glyph) and is decorative.
    const icon = screen.getByTestId("icon").parentElement!;
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).toHaveClass("[&_svg]:size-4", "h-5");
    expect(screen.getByRole("button", { name: "New post" })).toBeInTheDocument();
  });
});

describe("greeting", () => {
  it("follows the time of day", () => {
    expect(greeting(new Date(2026, 8, 28, 9), "Priya")).toBe("Good morning, Priya");
    expect(greeting(new Date(2026, 8, 28, 14), "Priya")).toBe("Good afternoon, Priya");
    expect(greeting(new Date(2026, 8, 28, 20))).toBe("Good evening");
  });
});
