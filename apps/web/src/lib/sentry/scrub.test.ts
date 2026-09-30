import type { Event } from "@sentry/nextjs";
import { afterEach, describe, expect, it, vi } from "vitest";

import { sampleRate, sentryOptions } from "./options";
import { scrubBreadcrumb, scrubEvent, scrubText, stripQuery } from "./scrub";

const TOKEN = "IGQWRPa1ZAabcdefghijklmnopqrstuvwxyz0123456789ABCDEFG";
const UUID = "5b1f7c1e-2c1b-4c0e-9a57-2f3f4a5b6c7d";

describe("scrubText (SEC-12)", () => {
  it("masks emails, bearer tokens, JWTs and long tokens but keeps ids", () => {
    // Built at runtime, so the secret scanner has no JWT-shaped literal to flag.
    const part = (value: object) =>
      btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
    const jwt = `${part({ alg: "RS256" })}.${part({ sub: "user_123" })}.c2lnbmF0dXJl`;
    const out = scrubText(
      `asha@example.com Bearer abc.def ${TOKEN} ${jwt} conversation ${UUID}`,
    );
    expect(out).toBe(`[email] Bearer [redacted] [token] [jwt] conversation ${UUID}`);
  });

  it("strips query strings", () => {
    expect(stripQuery("https://app.test/inbox?q=priya&token=1")).toBe("https://app.test/inbox");
  });
});

describe("scrubEvent (SEC-12)", () => {
  it("keeps only the request method and URL path, and the user id", () => {
    const event: Event = {
      request: {
        method: "GET",
        url: "https://app.test/inbox?q=priya",
        headers: { Authorization: "Bearer x", Cookie: "__session=1", Referer: "https://x" },
        cookies: { __session: "1" },
        data: { text: "Do you ship to Pune?" },
        query_string: "q=priya",
      },
      user: { id: "user_1", email: "asha@example.com", ip_address: "203.0.113.9" },
    };
    const out = scrubEvent(event);
    expect(out.request).toEqual({ method: "GET", url: "https://app.test/inbox" });
    expect(out.user).toEqual({ id: "user_1" });
  });

  it("scrubs exception messages, frame variables, extra and custom contexts", () => {
    const event: Event = {
      exception: {
        values: [
          {
            type: "Error",
            value: `send failed for asha@example.com with ${TOKEN}`,
            stacktrace: { frames: [{ function: "send", vars: { text: "hi" } }] },
          },
        ],
      },
      extra: { text: "Do you ship?", access_token: "t", status_code: 500, nested: [{ caption: "c" }] },
      contexts: {
        trace: { trace_id: "t1", span_id: "s1" },
        composer: { body: "draft", length: 12 },
      },
    };
    const out = scrubEvent(event);
    const exception = out.exception!.values![0]!;
    expect(exception.value).toBe("send failed for [email] with [token]");
    expect(exception.stacktrace!.frames![0]!.vars).toBeUndefined();
    expect(out.extra).toEqual({ access_token: "[redacted]", status_code: 500, nested: [{}] });
    expect(out.contexts).toEqual({
      trace: { trace_id: "t1", span_id: "s1" },
      composer: { length: 12 },
    });
  });

  it("strips query strings from breadcrumbs and spans", () => {
    const crumb = scrubBreadcrumb({
      category: "fetch",
      data: { url: "https://api.test/v1/w/1/search?q=priya", method: "GET", "http.query": "q=priya" },
    });
    expect(crumb.data).toEqual({ url: "https://api.test/v1/w/1/search", method: "GET" });
    const nav = scrubBreadcrumb({ category: "navigation", data: { from: "/a?x=1", to: "/b?y=2" } });
    expect(nav.data).toEqual({ from: "/a", to: "/b" });

    const out = scrubEvent({
      type: "transaction",
      spans: [
        {
          span_id: "s",
          trace_id: "t",
          start_timestamp: 0,
          description: "GET https://api.test/v1/me?token=abc",
          data: { url: "https://api.test/v1/me?token=abc" },
        },
      ],
    } as unknown as Event);
    expect(out.spans![0]!.description).toBe("GET https://api.test/v1/me");
    expect(out.spans![0]!.data).toEqual({ url: "https://api.test/v1/me" });
  });
});

describe("sentryOptions (T9.3)", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("is null without a DSN, so nothing is initialised", () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "");
    expect(sentryOptions()).toBeNull();
  });

  it("carries the environment, sample rate and scrubbers with a DSN", () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "https://public@o0.ingest.sentry.io/0");
    vi.stubEnv("NEXT_PUBLIC_SENTRY_ENVIRONMENT", "staging");
    vi.stubEnv("NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE", "0.2");
    const options = sentryOptions()!;
    expect(options.environment).toBe("staging");
    expect(options.tracesSampleRate).toBe(0.2);
    expect(options.sendDefaultPii).toBe(false);
    expect(options.beforeSend).toBe(scrubEvent);
  });

  it("ignores a sample rate outside 0 to 1", () => {
    expect(sampleRate("2")).toBe(0);
    expect(sampleRate("abc")).toBe(0);
    expect(sampleRate(undefined)).toBe(0);
    expect(sampleRate("1")).toBe(1);
  });
});
