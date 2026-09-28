import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { greeting } from "@/lib/copy";

import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";

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

describe("EmptyState", () => {
  it("renders title, body and action", () => {
    render(<EmptyState title="No notifications" body="We'll tell you." action={<button>Act</button>} />);
    expect(screen.getByText("No notifications")).toBeInTheDocument();
    expect(screen.getByText("We'll tell you.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
  });
});

describe("greeting", () => {
  it("follows the time of day", () => {
    expect(greeting(new Date(2026, 8, 28, 9), "Priya")).toBe("Good morning, Priya");
    expect(greeting(new Date(2026, 8, 28, 14), "Priya")).toBe("Good afternoon, Priya");
    expect(greeting(new Date(2026, 8, 28, 20))).toBe("Good evening");
  });
});
