import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import UnsubscribePage from "./page";
import { UnsubscribeResult } from "./UnsubscribeResult";

const TOKEN = "AQ".padEnd(66, "x");

describe("/unsubscribe (FR-NOT-04, C-049)", () => {
  it("posts the token once and says the digest is off for the workspace", async () => {
    const unsubscribe = vi.fn(async () => ({ status: 200, workspace: "Maple Bakery" }));
    render(<UnsubscribeResult token={TOKEN} unsubscribe={unsubscribe} />);
    expect(screen.getByRole("status")).toHaveTextContent("Unsubscribing…");
    expect(await screen.findByRole("heading", { name: "You're unsubscribed" })).toBeInTheDocument();
    expect(screen.getByText(/weekly digest for Maple Bakery/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Social Hood" })).toHaveAttribute("href", "/app");
    expect(unsubscribe).toHaveBeenCalledOnce();
    expect(unsubscribe).toHaveBeenCalledWith(TOKEN);
  });

  it("a token that doesn't verify (404) says the link doesn't work", async () => {
    render(<UnsubscribeResult token={TOKEN} unsubscribe={async () => ({ status: 404 })} />);
    expect(await screen.findByRole("heading", { name: "This link doesn't work" })).toBeInTheDocument();
  });

  it("a failure offers Try again", async () => {
    const user = userEvent.setup();
    const unsubscribe = vi
      .fn<(token: string) => Promise<{ status: number; workspace?: string }>>()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce({ status: 200, workspace: "Maple Bakery" });
    render(<UnsubscribeResult token={TOKEN} unsubscribe={unsubscribe} />);
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "You're unsubscribed" })).toBeInTheDocument());
    expect(unsubscribe).toHaveBeenCalledTimes(2);
  });

  it("no token, or a malformed one, sends nothing", async () => {
    render(await UnsubscribePage({ searchParams: Promise.resolve({}) }));
    expect(screen.getByRole("heading", { name: "This link is incomplete" })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
