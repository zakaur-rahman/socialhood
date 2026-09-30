/*
 * Social Hood service worker (TR-FE-09, FR-NOT-03). It does two things only: show a push
 * notification, and open its link when tapped. There is no fetch handler, so nothing is cached
 * and every request, API data included, goes to the network exactly as without a worker.
 *
 * The push payload (C-049) is JSON {title, body, url, tag}, where url is an app path such as
 * /w/maple/inbox/{conversation}.
 */

const FALLBACK_URL = "/app";

self.addEventListener("install", () => {
  // A new version takes over at once; it has no caches to migrate.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

/** Only paths on this origin are opened; anything else falls back to the app. */
function appUrl(value) {
  try {
    const url = new URL(typeof value === "string" && value ? value : FALLBACK_URL, self.location.origin);
    return url.origin === self.location.origin ? url.href : new URL(FALLBACK_URL, self.location.origin).href;
  } catch {
    return new URL(FALLBACK_URL, self.location.origin).href;
  }
}

function readPayload(data) {
  if (!data) return {};
  try {
    const parsed = data.json();
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return { body: data.text() };
  }
}

self.addEventListener("push", (event) => {
  const payload = readPayload(event.data);
  const title = typeof payload.title === "string" && payload.title ? payload.title : "Social Hood";
  const tag = typeof payload.tag === "string" && payload.tag ? payload.tag : undefined;
  const options = {
    body: typeof payload.body === "string" ? payload.body : "",
    icon: "/icons/icon-192.png",
    badge: "/icons/badge-72.png",
    data: { url: appUrl(payload.url) },
  };
  if (tag) {
    // A newer notification about the same thing replaces the old one and alerts again.
    options.tag = tag;
    options.renotify = true;
  }
  // userVisibleOnly: every push shows a notification, even one whose payload didn't parse.
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || appUrl(FALLBACK_URL);
  event.waitUntil(openOrFocus(target));
});

/** Focus a tab already showing the link; else take over an open app tab; else open a new one. */
async function openOrFocus(target) {
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  const same = windows.find((client) => client.url === target);
  if (same) return same.focus();
  const open = windows.find((client) => new URL(client.url).origin === self.location.origin);
  if (open) {
    try {
      const focused = await open.focus();
      if ("navigate" in focused) return await focused.navigate(target);
    } catch {
      // Not controlled by this worker (opened before it activated): open a new window instead.
    }
  }
  return self.clients.openWindow(target);
}
