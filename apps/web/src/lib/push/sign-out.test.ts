import { describe, expect, it, vi } from "vitest";

import { fakeApi, noContent } from "@/test/api";

import type { PushRegistration } from "./browser";
import { guardSignOut, removePushSubscription } from "./sign-out";

const ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc";

function registrationWith(subscription: { endpoint: string; unsubscribe: () => Promise<boolean> } | null) {
  return async () =>
    ({
      pushManager: { getSubscription: async () => subscription, subscribe: vi.fn() },
    }) as unknown as PushRegistration;
}

describe("removePushSubscription (sign-out on a shared device)", () => {
  it("deletes this browser's subscription from the API and unsubscribes it", async () => {
    const unsubscribe = vi.fn(async () => true);
    const { api, calls } = fakeApi({ "DELETE /v1/me/push-subscriptions": () => noContent() });
    await removePushSubscription(api, { registration: registrationWith({ endpoint: ENDPOINT, unsubscribe }) });
    expect(calls).toHaveLength(1);
    expect(calls[0].url.searchParams.get("endpoint")).toBe(ENDPOINT);
    expect(calls[0].headers.get("Authorization")).toBe("Bearer test-token"); // still signed in
    expect(unsubscribe).toHaveBeenCalledOnce();
  });

  it("nothing to do without a subscription or a worker", async () => {
    const { api, calls } = fakeApi({});
    await removePushSubscription(api, { registration: registrationWith(null) });
    await removePushSubscription(api, { registration: async () => null });
    expect(calls).toHaveLength(0);
  });

  it("never waits longer than the limit, and never throws", async () => {
    const { api } = fakeApi({ "DELETE /v1/me/push-subscriptions": () => new Promise<Response>(() => {}) });
    const started = Date.now();
    await removePushSubscription(api, {
      timeoutMs: 50,
      registration: registrationWith({ endpoint: ENDPOINT, unsubscribe: () => new Promise(() => {}) }),
    });
    expect(Date.now() - started).toBeLessThan(1_000);
    await expect(
      removePushSubscription(api, { registration: () => Promise.reject(new Error("no worker")) }),
    ).resolves.toBeUndefined();
  });
});

describe("guardSignOut", () => {
  function clerk() {
    const order: string[] = [];
    const target = {
      signOut: vi.fn(async function (this: unknown, ...args: unknown[]) {
        order.push("signOut");
        return args;
      }) as unknown as (...args: never[]) => Promise<unknown>,
    };
    return { target, order };
  }

  it("runs the clean-up first, then Clerk's sign-out with its arguments", async () => {
    const { target, order } = clerk();
    const original = target.signOut;
    guardSignOut(target, async () => {
      order.push("cleanup");
    });
    const result = await (target.signOut as unknown as (...args: unknown[]) => Promise<unknown>)({ redirectUrl: "/" });
    expect(order).toEqual(["cleanup", "signOut"]);
    expect(result).toEqual([{ redirectUrl: "/" }]);
    expect(vi.mocked(original).mock.contexts[0]).toBe(target);
  });

  it("signs out anyway when the clean-up fails or hangs (at most the limit)", async () => {
    const failing = clerk();
    guardSignOut(failing.target, () => Promise.reject(new Error("offline")));
    await failing.target.signOut();
    expect(failing.order).toEqual(["signOut"]);

    const hanging = clerk();
    guardSignOut(hanging.target, () => new Promise(() => {}), 50);
    const started = Date.now();
    await hanging.target.signOut();
    expect(hanging.order).toEqual(["signOut"]);
    expect(Date.now() - started).toBeLessThan(1_000);
  });

  it("wraps once, and can be undone", async () => {
    const { target, order } = clerk();
    const original = target.signOut;
    const cleanup = vi.fn(async () => {});
    const undo = guardSignOut(target, cleanup);
    guardSignOut(target, cleanup); // a second mount doesn't wrap again
    await target.signOut();
    expect(cleanup).toHaveBeenCalledOnce();
    undo();
    expect(target.signOut).toBe(original);
    expect(order).toEqual(["signOut"]);
  });
});
