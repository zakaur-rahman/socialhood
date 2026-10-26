import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnswerText } from "@/components/agent/AnswerText";
import { MessageBubble } from "@/components/inbox/MessageBubble";
import { browser, webUrl } from "@/lib/billing/browser";
import { message } from "@/test/api";

import { clerkFrontendApi, contentSecurityPolicy, originOf, securityHeaders } from "./headers";

// T9.2 security pass (SEC-08, SEC-11): headers, navigation to API-supplied URLs, and user or
// model text that looks like HTML.

const PAYLOAD = '<img src=x onerror="alert(1)"><script>alert(2)</script><a href="javascript:alert(3)">x</a>';

const PRODUCTION = {
  NODE_ENV: "production",
  NEXT_PUBLIC_API_BASE_URL: "https://api.amplychat.com",
  // pk_live_ + base64("clerk.amplychat.com$")
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: `pk_live_${btoa("clerk.amplychat.com$")}`,
  NEXT_PUBLIC_SENTRY_DSN: "https://abc123@o42.ingest.us.sentry.io/7",
};

function directive(csp: string, name: string): string[] {
  const found = csp.split("; ").find((part) => part.startsWith(`${name} `));
  return found ? found.split(" ").slice(1) : [];
}

describe("the web CSP (SEC-11)", () => {
  const csp = contentSecurityPolicy(PRODUCTION);

  it("allows the app, the API, Clerk, Cloudinary, Sentry and Meta's SDK, nothing else by default", () => {
    expect(directive(csp, "default-src")).toEqual(["'self'"]);
    expect(directive(csp, "connect-src")).toEqual(
      expect.arrayContaining([
        "'self'",
        "https://api.amplychat.com",
        "https://clerk.amplychat.com",
        "https://api.cloudinary.com",
        "https://o42.ingest.us.sentry.io",
      ]),
    );
    expect(directive(csp, "script-src")).toEqual(
      expect.arrayContaining(["https://clerk.amplychat.com", "https://connect.facebook.net"]),
    );
    expect(directive(csp, "img-src")).toContain("https://res.cloudinary.com");
  });

  it("cannot be framed, has no plugins or base rewrites, and is strict in production", () => {
    expect(directive(csp, "frame-ancestors")).toEqual(["'none'"]);
    expect(directive(csp, "object-src")).toEqual(["'none'"]);
    expect(directive(csp, "base-uri")).toEqual(["'self'"]);
    expect(directive(csp, "script-src")).not.toContain("'unsafe-eval'");
    expect(csp).toContain("upgrade-insecure-requests");
    // A local production build (the Playwright run: web :3100, API :8100) follows its API origin.
    const local = { ...PRODUCTION, NEXT_PUBLIC_API_BASE_URL: "http://localhost:8100" };
    expect(contentSecurityPolicy(local)).not.toContain("upgrade-insecure-requests");
    expect(directive(contentSecurityPolicy(local), "connect-src")).toContain("http://localhost:8100");
    expect(contentSecurityPolicy({ ...PRODUCTION, NODE_ENV: "development" })).toContain("'unsafe-eval'");
  });

  it("ignores values that aren't web origins", () => {
    expect(originOf("javascript:alert(1)")).toBeNull();
    expect(originOf("not a url")).toBeNull();
    expect(originOf(undefined)).toBeNull();
    expect(clerkFrontendApi("pk_test_")).toBeNull();
    expect(clerkFrontendApi(`pk_test_${btoa("evil.example; script-src *$")}`)).toBeNull();
    const csp = contentSecurityPolicy({ NODE_ENV: "production" });
    expect(csp).not.toContain("null");
    expect(csp).not.toContain("undefined");
  });

  it("sends the other headers", () => {
    const headers = Object.fromEntries(securityHeaders(PRODUCTION).map((h) => [h.key, h.value]));
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["Strict-Transport-Security"]).toMatch(/^max-age=\d+/);
    expect(headers["Permissions-Policy"]).toContain("camera=()");
    expect(headers["X-Permitted-Cross-Domain-Policies"]).toBe("none");
    expect(headers["Cross-Origin-Opener-Policy"]).toBe("same-origin-allow-popups");
  });

  it("sends HSTS the preload list accepts: a year or more, every subdomain, preload (C-143)", () => {
    const hsts = Object.fromEntries(securityHeaders(PRODUCTION).map((h) => [h.key, h.value]))[
      "Strict-Transport-Security"
    ];
    const maxAge = Number(/max-age=(\d+)/.exec(hsts)?.[1]);
    expect(maxAge).toBeGreaterThanOrEqual(31536000);
    expect(hsts).toContain("includeSubDomains");
    expect(hsts).toContain("preload");
  });

  it("turns off every powerful feature the app doesn't use", () => {
    const policy = Object.fromEntries(securityHeaders(PRODUCTION).map((h) => [h.key, h.value]))["Permissions-Policy"];
    for (const feature of ["camera", "microphone", "geolocation", "payment", "usb", "browsing-topics"]) {
      expect(policy).toContain(`${feature}=()`);
    }
    // Nothing is switched on: every entry is the empty allowlist.
    expect(policy.split(", ").every((entry) => entry.endsWith("=()"))).toBe(true);
  });

  it("keeps 'unsafe-inline' to scripts and styles, and eval out of production", () => {
    const withInline = csp
      .split("; ")
      .filter((part) => part.includes("'unsafe-inline'"))
      .map((part) => part.split(" ")[0]);
    expect(withInline).toEqual(["script-src", "style-src"]);
    expect(csp).not.toContain("'unsafe-eval'");
    expect(csp).not.toMatch(/(^|\s)\*(\s|;|$)/); // no bare wildcard source
  });

  it("upgrades requests on the website-only Vercel launch, which has no API yet", () => {
    const websiteOnly = { NODE_ENV: "production", VERCEL: "1" };
    expect(contentSecurityPolicy(websiteOnly)).toContain("upgrade-insecure-requests");
    expect(contentSecurityPolicy({ NODE_ENV: "production" })).not.toContain("upgrade-insecure-requests");
    // Without an API the policy still allows only the site and its vendors.
    expect(directive(contentSecurityPolicy(websiteOnly), "connect-src")).not.toContain("http://localhost:8000");
  });

  it("follows a Clerk development key to its accounts.dev host", () => {
    const dev = contentSecurityPolicy({
      ...PRODUCTION,
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: `pk_test_${btoa("calm-fox-12.clerk.accounts.dev$")}`,
    });
    expect(directive(dev, "script-src")).toContain("https://calm-fox-12.clerk.accounts.dev");
    expect(directive(dev, "connect-src")).toContain("https://calm-fox-12.clerk.accounts.dev");
  });
});

describe("leaving the app for a URL the API gave", () => {
  it("only goes to web pages", () => {
    expect(webUrl("https://checkout.dodopayments.com/s/abc")).toBe("https://checkout.dodopayments.com/s/abc");
    for (const url of ["javascript:alert(1)", "data:text/html,<script>alert(1)</script>", "/relative"]) {
      expect(() => webUrl(url)).toThrow();
    }
  });

  it("refuses to navigate or fill the portal tab with anything else", () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    try {
      expect(() => browser.assign("javascript:alert(1)")).toThrow();
      const tab = { closed: false, opener: null, location: { href: "" }, close: vi.fn() };
      vi.spyOn(window, "open").mockReturnValue(tab as unknown as Window);
      const pending = browser.openPending();
      expect(() => pending.go("javascript:alert(1)")).toThrow();
      expect(tab.location.href).toBe("");
      expect(tab.close).toHaveBeenCalled();
      expect(assign).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
      vi.restoreAllMocks();
    }
  });
});

describe("text that looks like HTML is shown as text (SEC-08)", () => {
  it("in an Ask Amplychat answer", () => {
    const { container } = render(<AnswerText answer={`Here you go **${PAYLOAD}**`} refs={[]} slug="acme" />);
    expect(container.querySelector("img, script, a, iframe")).toBeNull();
    expect(container.textContent).toContain(PAYLOAD);
  });

  it("in a customer's message", () => {
    const { container } = render(
      <MessageBubble
        message={message({ text: PAYLOAD })}
        platform="instagram"
        timeZone="UTC"
        contact={{ id: "p1", name: "Priya", pictureUrl: null }}
        groupEnd={false}
      />,
    );
    expect(container.querySelector("script, iframe, a[href^='javascript']")).toBeNull();
    expect(container.querySelector("img[src='x']")).toBeNull();
    expect(container.textContent).toContain(PAYLOAD);
  });
});
