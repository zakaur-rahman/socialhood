import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PushConfig } from "@/lib/api/types";
import type { PushBrowser } from "@/lib/push/browser";
import type { PushEnvironment } from "@/lib/push/support";
import { json, noContent, renderWithApi } from "@/test/api";

import { PushSetup } from "./PushSetup";

const VAPID = "BAECAwQ"; // bytes 4, 1, 2, 3, 4

type FakeSubscription = PushSubscription & { unsubscribe: ReturnType<typeof vi.fn> };

function fakeSubscription(endpoint = "https://fcm.googleapis.com/fcm/send/abc"): FakeSubscription {
  return {
    endpoint,
    options: { applicationServerKey: new Uint8Array([4, 1, 2, 3, 4]).buffer, userVisibleOnly: true },
    toJSON: () => ({ endpoint, keys: { p256dh: "BPk-key", auth: "auth-secret" } }),
    unsubscribe: vi.fn(async () => true),
  } as unknown as FakeSubscription;
}

function fakeBrowser({
  env = {},
  existing = null,
  answer = "granted",
  enabled = true,
}: {
  env?: Partial<PushEnvironment>;
  existing?: FakeSubscription | null;
  answer?: NotificationPermission;
  enabled?: boolean;
} = {}) {
  let current = existing;
  const created = fakeSubscription();
  const subscribe = vi.fn(async () => {
    current = created;
    return created;
  });
  const requestPermission = vi.fn(async () => answer);
  const browser: PushBrowser = {
    environment: () => ({ platform: "android", standalone: false, pushApis: true, permission: "default", ...env }),
    enabled: () => enabled,
    registration: async () => ({
      pushManager: {
        getSubscription: async () => current,
        subscribe,
      } as unknown as PushManager,
    }),
    requestPermission,
  };
  return { browser, subscribe, requestPermission, created };
}

function setup(browser: PushBrowser, { config = { enabled: true, vapid_public_key: VAPID } }: { config?: PushConfig } = {}) {
  return renderWithApi(<PushSetup browser={browser} />, {
    handlers: {
      "GET /v1/push/config": () => json(config),
      "POST /v1/me/push-subscriptions": () =>
        json({ id: "d1", user_agent: "test", created_at: "2026-09-30T06:00:00Z", last_used_at: null }, 201),
      "DELETE /v1/me/push-subscriptions": () => noContent(),
    },
  });
}

describe("PushSetup: this device's push (UX-SCR-07, F-19)", () => {
  it("off: turning on asks for permission in the click, subscribes with the API's key and registers", async () => {
    const user = userEvent.setup();
    const fake = fakeBrowser();
    const { calls } = setup(fake.browser);
    const toggle = await screen.findByRole("switch", { name: "Notifications on this device" });
    expect(toggle).not.toBeChecked();
    expect(fake.requestPermission).not.toHaveBeenCalled(); // never before the member asks

    await user.click(toggle);
    await waitFor(() => expect(screen.getByRole("switch", { name: "Notifications on this device" })).toBeChecked());
    expect(fake.requestPermission).toHaveBeenCalledOnce();
    const options = fake.subscribe.mock.calls[0] as unknown as [PushSubscriptionOptionsInit];
    expect(options[0].userVisibleOnly).toBe(true);
    expect(Array.from(options[0].applicationServerKey as Uint8Array)).toEqual([4, 1, 2, 3, 4]);
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe("/v1/me/push-subscriptions");
    expect(post?.body).toMatchObject({
      endpoint: "https://fcm.googleapis.com/fcm/send/abc",
      keys: { p256dh: "BPk-key", auth: "auth-secret" },
    });
  });

  it("on: turning off removes it from the API and unsubscribes", async () => {
    const user = userEvent.setup();
    const existing = fakeSubscription("https://updates.push.services.mozilla.com/wpush/v2/xyz");
    const fake = fakeBrowser({ env: { permission: "granted" }, existing });
    const { calls } = setup(fake.browser);
    const toggle = await screen.findByRole("switch", { name: "Notifications on this device" });
    await waitFor(() => expect(toggle).toBeChecked());
    await user.click(toggle);
    await waitFor(() => expect(existing.unsubscribe).toHaveBeenCalled());
    const del = calls.find((c) => c.method === "DELETE");
    expect(del?.url.searchParams.get("endpoint")).toBe("https://updates.push.services.mozilla.com/wpush/v2/xyz");
    await waitFor(() => expect(screen.getByRole("switch", { name: "Notifications on this device" })).not.toBeChecked());
  });

  it("the member says no: blocked, with how to allow it again", async () => {
    const user = userEvent.setup();
    const fake = fakeBrowser({ answer: "denied" });
    setup(fake.browser);
    await user.click(await screen.findByRole("switch", { name: "Notifications on this device" }));
    expect(await screen.findByText("Notifications are blocked for Social Hood")).toBeInTheDocument();
    expect(screen.getByText(/Permissions, and allow Notifications/)).toBeInTheDocument();
    expect(fake.subscribe).not.toHaveBeenCalled();
  });

  it("already blocked on an installed Android app: the app-info steps", async () => {
    setup(fakeBrowser({ env: { permission: "denied", standalone: true } }).browser);
    expect(await screen.findByText("Notifications are blocked for Social Hood")).toBeInTheDocument();
    expect(screen.getByText(/Touch and hold the Social Hood icon/)).toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
  });

  it("iPhone in Safari: add to the Home Screen first, with the two steps", async () => {
    setup(fakeBrowser({ env: { platform: "ios", pushApis: false } }).browser);
    expect(await screen.findByText("Add Social Hood to your Home Screen first")).toBeInTheDocument();
    const steps = screen.getByRole("list", { name: "Add Social Hood to your Home Screen" });
    expect(steps).toHaveTextContent("Tap Share in Safari's toolbar.");
    expect(steps).toHaveTextContent("Choose Add to Home Screen");
  });

  it("blocked on iPhone: the Settings app steps", async () => {
    setup(fakeBrowser({ env: { platform: "ios", standalone: true, permission: "denied" } }).browser);
    expect(await screen.findByText(/Open the Settings app, tap Notifications/)).toBeInTheDocument();
  });

  it("a browser without push says so", async () => {
    setup(fakeBrowser({ env: { platform: "desktop", pushApis: false } }).browser);
    expect(await screen.findByText("This browser can't show notifications from Social Hood")).toBeInTheDocument();
  });

  it("unavailable when the API has no VAPID keys, or this build has no service worker", async () => {
    const first = setup(fakeBrowser().browser, { config: { enabled: false, vapid_public_key: null } });
    expect(await screen.findByText("Phone notifications aren't available right now")).toBeInTheDocument();
    first.unmount();
    setup(fakeBrowser({ enabled: false }).browser);
    expect(await screen.findByText("Phone notifications aren't available right now")).toBeInTheDocument();
  });

  it("if the API refuses the subscription, the browser's is dropped and it says so", async () => {
    const user = userEvent.setup();
    const fake = fakeBrowser();
    renderWithApi(<PushSetup browser={fake.browser} />, {
      handlers: {
        "GET /v1/push/config": () => json({ enabled: true, vapid_public_key: VAPID }),
        "POST /v1/me/push-subscriptions": () => new Response("nope", { status: 500 }),
      },
    });
    await user.click(await screen.findByRole("switch", { name: "Notifications on this device" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on our side");
    expect(fake.created.unsubscribe).toHaveBeenCalled();
    expect(screen.getByRole("switch", { name: "Notifications on this device" })).not.toBeChecked();
  });
});
