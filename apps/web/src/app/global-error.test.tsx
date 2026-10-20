import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import GlobalError from "./global-error";

const sentry = vi.hoisted(() => ({ captureException: vi.fn() }));
vi.mock("@sentry/nextjs", () => sentry);

describe("the global error boundary (RG-07)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reports the error to Sentry and offers Try again", async () => {
    sentry.captureException.mockClear();
    // <html> inside the test container is a DOM-nesting warning in jsdom; the boundary needs it.
    vi.spyOn(console, "error").mockImplementation(() => {});
    const retry = vi.fn();
    const error = new Error("layout crashed");
    render(<GlobalError error={error} retry={retry} />);
    expect(sentry.captureException).toHaveBeenCalledExactlyOnceWith(error);
    expect(screen.getByRole("alert")).toHaveTextContent("This didn't load");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
