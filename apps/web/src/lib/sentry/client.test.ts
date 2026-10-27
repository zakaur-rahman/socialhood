import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { captureError, loadSentry, loadedSentry, resetSentryForTests, startSentry } from "./client";

const sentry = vi.hoisted(() => ({ init: vi.fn(), captureException: vi.fn() }));
vi.mock("@sentry/nextjs", () => sentry);

const DSN = "https://public@o0.ingest.sentry.io/0";

describe("the browser's Sentry, loaded on demand (C-148)", () => {
  beforeEach(() => {
    sentry.init.mockClear();
    sentry.captureException.mockClear();
    resetSentryForTests();
  });
  afterEach(() => vi.unstubAllEnvs());

  it("loads nothing without a DSN", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "");
    expect(await loadSentry()).toBeNull();
    captureError(new Error("x"));
    startSentry("/app");
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(sentry.init).not.toHaveBeenCalled();
    expect(sentry.captureException).not.toHaveBeenCalled();
  });

  it("initialises once, then reports", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", DSN);
    const error = new Error("boom");
    captureError(error);
    await loadSentry();
    await vi.waitFor(() => expect(sentry.captureException).toHaveBeenCalledWith(error));
    expect(sentry.init).toHaveBeenCalledOnce();
    expect(sentry.init.mock.calls[0]![0]).toMatchObject({ dsn: DSN, sendDefaultPii: false });
    expect(loadedSentry()).not.toBeNull();
  });

  it("starts at once in the app", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", DSN);
    startSentry("/w/acme/inbox", 60_000);
    await vi.waitFor(() => expect(sentry.init).toHaveBeenCalledOnce());
  });

  it("waits for idle on a public page, but reports an error that comes first", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", DSN);
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    startSentry("/pricing", 60_000);
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(sentry.init).not.toHaveBeenCalled();

    // The early listener (called directly: a dispatched error event would fail the test run).
    const early = add.mock.calls.find(([type]) => type === "error")![1] as (event: ErrorEvent) => void;
    const error = new Error("early");
    early(new ErrorEvent("error", { error, message: "early" }));
    await vi.waitFor(() => expect(sentry.captureException).toHaveBeenCalledExactlyOnceWith(error));
    expect(sentry.init).toHaveBeenCalledOnce();

    // Once the SDK runs, its own handlers report; the early listeners are gone.
    await vi.waitFor(() => expect(remove).toHaveBeenCalledWith("error", early));
    expect(remove).toHaveBeenCalledWith("unhandledrejection", early);
    add.mockRestore();
    remove.mockRestore();
  });

  it("loads on a public page once the browser is idle", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", DSN);
    startSentry("/", 5);
    await vi.waitFor(() => expect(sentry.init).toHaveBeenCalledOnce());
  });
});
