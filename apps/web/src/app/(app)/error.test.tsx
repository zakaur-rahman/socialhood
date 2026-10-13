import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SignedInError from "./error";

const sentry = vi.hoisted(() => ({ captureException: vi.fn() }));
vi.mock("@sentry/nextjs", () => sentry);

describe("the signed-in error boundary (RG-07)", () => {
  it("reports the error to Sentry once and keeps the ErrorState", async () => {
    sentry.captureException.mockClear();
    const reset = vi.fn();
    const error = new Error("boom");
    render(<SignedInError error={error} reset={reset} />);
    expect(sentry.captureException).toHaveBeenCalledExactlyOnceWith(error);
    expect(screen.getByRole("alert")).toHaveTextContent("This didn't load");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
