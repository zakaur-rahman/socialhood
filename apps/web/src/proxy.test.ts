import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Clerk's middleware is replaced by a pass-through that hands the request to our handler with a
// fake `auth`, so these tests see only the host routing (C-146) and the sign-in guard.
const protect = vi.fn(async () => undefined);
const options = vi.fn();
const clerkRan = vi.fn();
vi.mock("@clerk/nextjs/server", () => ({
  clerkMiddleware: (handler: (auth: unknown, request: NextRequest) => unknown, opts: unknown) => {
    options(opts);
    return (request: NextRequest) => {
      clerkRan(request.nextUrl.pathname);
      return handler({ protect }, request);
    };
  },
  createRouteMatcher: (patterns: string[]) => (request: NextRequest) =>
    patterns.some((pattern) => new RegExp(`^${pattern}$`).test(request.nextUrl.pathname)),
}));

async function loadProxy(appUrl: string | undefined) {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_APP_URL", appUrl ?? "");
  vi.stubEnv("NEXT_PUBLIC_SITE_URL", "");
  const proxy = (await import("./proxy")).default as unknown as (request: NextRequest, event: unknown) => Promise<Response | undefined>;
  return (request: NextRequest) => proxy(request, {});
}

function request(url: string): NextRequest {
  return new NextRequest(url, { headers: { host: new URL(url).host } });
}

beforeEach(() => {
  protect.mockClear();
  options.mockClear();
  clerkRan.mockClear();
});
afterEach(() => vi.unstubAllEnvs());

describe("proxy with NEXT_PUBLIC_APP_URL unset (one origin)", () => {
  it("redirects nothing and still guards the app", async () => {
    const proxy = await loadProxy(undefined);
    expect(await proxy(request("http://localhost:3000/pricing"))).toBeUndefined();
    expect(await proxy(request("http://localhost:3000/sign-in"))).toBeUndefined();
    expect(await proxy(request("http://localhost:3000/app"))).toBeUndefined();
    expect(protect).toHaveBeenCalledOnce();
    expect(clerkRan).toHaveBeenCalledTimes(3);
    expect(options).toHaveBeenCalledWith({ authorizedParties: undefined });
  });
});

describe("proxy with the app on dashboard.amplychat.com", () => {
  const APP = "https://dashboard.amplychat.com";

  it("tells Clerk both origins are authorized parties", async () => {
    await loadProxy(APP);
    expect(options).toHaveBeenCalledWith({ authorizedParties: ["https://amplychat.com", APP] });
  });

  it("moves app pages off the site with a 308, before asking for a session", async () => {
    const proxy = await loadProxy(APP);
    const response = await proxy(request("https://amplychat.com/w/maple/inbox?c=1"));
    expect(response?.status).toBe(308);
    expect(response?.headers.get("location")).toBe(`${APP}/w/maple/inbox?c=1`);
    expect(protect).not.toHaveBeenCalled();
  });

  it("lets the public site through without running Clerk (C-152)", async () => {
    const proxy = await loadProxy(APP);
    for (const path of ["/", "/pricing", "/privacy?x=1"]) {
      const response = await proxy(request(`https://amplychat.com${path}`));
      expect(response?.status).toBe(200);
      expect(response?.headers.get("x-middleware-next")).toBe("1");
      expect(response?.headers.get("x-robots-tag")).toBeNull();
    }
    expect(clerkRan).not.toHaveBeenCalled();
    expect(protect).not.toHaveBeenCalled();
  });

  it("moves public pages off the app host and sends its home to /app", async () => {
    const proxy = await loadProxy(APP);
    const pricing = await proxy(request(`${APP}/pricing`));
    expect(pricing?.status).toBe(308);
    expect(pricing?.headers.get("location")).toBe("https://amplychat.com/pricing");
    const home = await proxy(request(`${APP}/`));
    expect(home?.status).toBe(307);
    expect(home?.headers.get("location")).toBe(`${APP}/app`);
  });

  it("guards the app on the app host and marks it noindex", async () => {
    const proxy = await loadProxy(APP);
    const response = await proxy(request(`${APP}/app`));
    expect(protect).toHaveBeenCalledOnce();
    expect(response?.headers.get("x-robots-tag")).toBe("noindex, nofollow");
    expect((await proxy(request(`${APP}/sign-in`)))?.headers.get("x-robots-tag")).toBe("noindex, nofollow");
  });

  it("answers robots.txt with disallow-all and 404s the sitemap on the app host", async () => {
    const proxy = await loadProxy(APP);
    const robots = await proxy(request(`${APP}/robots.txt`));
    expect(robots?.status).toBe(200);
    expect(await robots?.text()).toBe("User-agent: *\nDisallow: /\n");
    expect((await proxy(request(`${APP}/sitemap.xml`)))?.status).toBe(404);
  });
});
