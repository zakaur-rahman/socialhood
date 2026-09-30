/**
 * public/sw.js (TR-FE-09) run in a sandbox with a fake service worker scope: it shows a
 * notification for a push and opens its link on click. It must not handle fetch (no caching).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

import { describe, expect, it, vi } from "vitest";

const source = readFileSync(join(process.cwd(), "public", "sw.js"), "utf8");
const ORIGIN = "https://app.socialhood.com";

type Listener = (event: Record<string, unknown>) => void;

type FakeClient = {
  url: string;
  focus: ReturnType<typeof vi.fn<() => Promise<unknown>>>;
  navigate: ReturnType<typeof vi.fn<(url: string) => Promise<unknown>>>;
};

function worker(windows: { url: string; navigate?: (url: string) => Promise<unknown> }[] = []) {
  const listeners = new Map<string, Listener>();
  const showNotification = vi.fn(async () => {});
  const openWindow = vi.fn(async () => null);
  const clients = windows.map((w) => {
    const client: FakeClient = {
      url: w.url,
      focus: vi.fn<() => Promise<unknown>>(async () => client),
      navigate: vi.fn<(url: string) => Promise<unknown>>(w.navigate ?? (async () => client)),
    };
    return client;
  });
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, listener: Listener) => listeners.set(type, listener),
    skipWaiting: vi.fn(),
    registration: { showNotification },
    clients: { claim: vi.fn(async () => {}), matchAll: vi.fn(async () => clients), openWindow },
  };
  runInNewContext(source, { self, URL, console });
  const fire = async (type: string, event: Record<string, unknown>) => {
    let pending: Promise<unknown> = Promise.resolve();
    listeners.get(type)?.({ ...event, waitUntil: (p: Promise<unknown>) => (pending = p) });
    await pending;
  };
  return { listeners, showNotification, openWindow, clients, fire };
}

function pushEvent(payload: unknown) {
  const text = typeof payload === "string" ? payload : JSON.stringify(payload);
  return {
    data: {
      json: () => JSON.parse(text),
      text: () => text,
    },
  };
}

describe("service worker (TR-FE-09)", () => {
  it("handles push and notificationclick only: no fetch handler, so nothing is cached", () => {
    const { listeners } = worker();
    expect([...listeners.keys()].sort()).toEqual(["activate", "install", "notificationclick", "push"]);
  });

  it("shows the notification from {title, body, url, tag}", async () => {
    const sw = worker();
    await sw.fire(
      "push",
      pushEvent({ title: "Priya needs you", body: "Asked for a refund", url: "/w/maple/inbox/c1", tag: "conversation:c1" }),
    );
    expect(sw.showNotification).toHaveBeenCalledWith("Priya needs you", {
      body: "Asked for a refund",
      icon: "/icons/icon-192.png",
      badge: "/icons/badge-72.png",
      data: { url: `${ORIGIN}/w/maple/inbox/c1` },
      tag: "conversation:c1",
      renotify: true,
    });
  });

  it("always shows something, and never opens another site", async () => {
    const sw = worker();
    await sw.fire("push", pushEvent("not json"));
    expect(sw.showNotification).toHaveBeenLastCalledWith("Social Hood", expect.objectContaining({ body: "not json" }));
    await sw.fire("push", pushEvent({ title: "Hi", url: "https://evil.example/phish" }));
    expect(sw.showNotification).toHaveBeenLastCalledWith("Hi", expect.objectContaining({ data: { url: `${ORIGIN}/app` } }));
  });

  function click(url: string) {
    const close = vi.fn();
    return { notification: { close, data: { url } }, close };
  }

  it("a tap focuses a tab already on the link", async () => {
    const sw = worker([{ url: `${ORIGIN}/w/maple/home` }, { url: `${ORIGIN}/w/maple/inbox/c1` }]);
    const event = click(`${ORIGIN}/w/maple/inbox/c1`);
    await sw.fire("notificationclick", event);
    expect(event.close).toHaveBeenCalled();
    expect(sw.clients[1].focus).toHaveBeenCalled();
    expect(sw.clients[0].navigate).not.toHaveBeenCalled();
    expect(sw.openWindow).not.toHaveBeenCalled();
  });

  it("otherwise takes over an open app tab, or opens a window", async () => {
    const open = worker([{ url: `${ORIGIN}/w/maple/home` }]);
    await open.fire("notificationclick", click(`${ORIGIN}/w/maple/inbox/c1`));
    expect(open.clients[0].focus).toHaveBeenCalled();
    expect(open.clients[0].navigate).toHaveBeenCalledWith(`${ORIGIN}/w/maple/inbox/c1`);

    const none = worker();
    await none.fire("notificationclick", click(`${ORIGIN}/w/maple/inbox/c1`));
    expect(none.openWindow).toHaveBeenCalledWith(`${ORIGIN}/w/maple/inbox/c1`);

    const uncontrolled = worker([
      { url: `${ORIGIN}/`, navigate: async () => Promise.reject(new TypeError("not controlled")) },
    ]);
    await uncontrolled.fire("notificationclick", click(`${ORIGIN}/w/maple/inbox/c1`));
    expect(uncontrolled.openWindow).toHaveBeenCalledWith(`${ORIGIN}/w/maple/inbox/c1`);
  });
});
