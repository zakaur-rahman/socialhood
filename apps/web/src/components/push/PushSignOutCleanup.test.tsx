import { waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { noContent, renderWithApi } from "@/test/api";

import { PushSignOutCleanup } from "./PushSignOutCleanup";

const ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc";

// Clerk's loaded instance, the one its UserButton menu calls, behind useClerk()'s wrapper.
const clerk = vi.hoisted(() => {
  const order: string[] = [];
  const instance: { signOut: (options?: { redirectUrl?: string }) => Promise<void> } = {
    signOut: async () => {
      order.push("signOut");
    },
  };
  return { order, instance, wrapper: { loaded: true, clerkjs: instance } };
});
vi.mock("@clerk/nextjs", () => ({ useClerk: () => clerk.wrapper }));

const unsubscribe = vi.fn(async () => {
  clerk.order.push("unsubscribe");
  return true;
});

beforeEach(() => {
  clerk.order.length = 0;
  unsubscribe.mockClear();
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: {
      getRegistration: async () => ({
        pushManager: { getSubscription: async () => ({ endpoint: ENDPOINT, unsubscribe }) },
      }),
    },
  });
});

afterEach(() => {
  Reflect.deleteProperty(navigator, "serviceWorker");
});

describe("sign-out removes this browser's push first (shared devices)", () => {
  it("UserButton's sign-out (Clerk's instance) deletes and unsubscribes, then signs out", async () => {
    const { calls, unmount } = renderWithApi(<PushSignOutCleanup />, {
      handlers: {
        "DELETE /v1/me/push-subscriptions": () => {
          clerk.order.push("delete");
          return noContent();
        },
      },
    });
    await waitFor(() => expect(clerk.instance.signOut.name).toBe("guardedSignOut"));

    await clerk.instance.signOut({ redirectUrl: "/" });
    expect(calls.find((c) => c.method === "DELETE")?.url.searchParams.get("endpoint")).toBe(ENDPOINT);
    expect(unsubscribe).toHaveBeenCalledOnce();
    expect(clerk.order.at(-1)).toBe("signOut");
    expect(clerk.order.slice(0, 2).sort()).toEqual(["delete", "unsubscribe"]);

    // Leaving the signed-in app puts Clerk's method back.
    unmount();
    expect(clerk.instance.signOut.name).not.toBe("guardedSignOut");
  });

  it("an API that doesn't answer doesn't keep the member signed in", async () => {
    renderWithApi(<PushSignOutCleanup />, {
      handlers: { "DELETE /v1/me/push-subscriptions": () => new Promise<Response>(() => {}) },
    });
    await waitFor(() => expect(clerk.instance.signOut.name).toBe("guardedSignOut"));
    const started = Date.now();
    await clerk.instance.signOut();
    expect(clerk.order).toContain("signOut");
    expect(Date.now() - started).toBeLessThan(2_600);
  }, 10_000);
});
