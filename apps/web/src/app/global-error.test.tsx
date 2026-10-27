import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetSentryForTests } from "@/lib/sentry/client";

import GlobalError from "./global-error";

const sentry = vi.hoisted(() => ({ captureException: vi.fn(), init: vi.fn() }));
vi.mock("@sentry/nextjs", () => sentry);

describe("the global error boundary (RG-07)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    resetSentryForTests();
  });

  it("reports the error to Sentry and offers Try again", async () => {
    sentry.captureException.mockClear();
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "https://public@o0.ingest.sentry.io/0");
    // <html> inside the test container is a DOM-nesting warning in jsdom; the boundary needs it.
    vi.spyOn(console, "error").mockImplementation(() => {});
    const retry = vi.fn();
    const error = new Error("layout crashed");
    render(<GlobalError error={error} retry={retry} />);
    // The SDK loads on demand (C-148), then initialises and reports.
    await waitFor(() => expect(sentry.captureException).toHaveBeenCalledExactlyOnceWith(error));
    expect(sentry.init).toHaveBeenCalledOnce();
    expect(screen.getByRole("alert")).toHaveTextContent("This didn't load");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
