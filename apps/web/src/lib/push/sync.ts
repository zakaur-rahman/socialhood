import type { Api } from "@/lib/api/client";

import { registerServiceWorker, serviceWorkerEnabled, subscriptionBody } from "./browser";
import { base64UrlToBytes, sameKey } from "./support";

const SYNCED_KEY = "socialhood:push-synced";

function syncedEndpoint(): string | null {
  try {
    return window.sessionStorage.getItem(SYNCED_KEY);
  } catch {
    return null;
  }
}

function markSynced(endpoint: string) {
  try {
    window.sessionStorage.setItem(SYNCED_KEY, endpoint);
  } catch {
    // Synced again next page load; registering is idempotent.
  }
}

/**
 * On each visit (TR-FE-09, C-049): register /sw.js, and if this browser already has push on,
 * register its subscription again. That refreshes it (clearing a disabled state), gives the
 * device to whoever is signed in now, and replaces it when the API's VAPID key has changed. It
 * never asks for permission; that happens only from a click in Settings → Notifications.
 */
export async function syncPushSubscription(api: Api): Promise<void> {
  if (!serviceWorkerEnabled()) return;
  const registration = await registerServiceWorker();
  if (!registration || !("Notification" in window) || Notification.permission !== "granted") return;
  if (!("pushManager" in registration)) return;
  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;
  const { data: config } = await api.GET("/v1/push/config");
  const key = config?.enabled ? config.vapid_public_key : null;
  if (!key) return;
  if (!sameKey(subscription.options?.applicationServerKey, key)) {
    await subscription.unsubscribe();
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: base64UrlToBytes(key),
    });
  } else if (syncedEndpoint() === subscription.endpoint) {
    return;
  }
  const { response } = await api.POST("/v1/me/push-subscriptions", {
    body: subscriptionBody(subscription, navigator.userAgent),
  });
  if (response.ok) markSynced(subscription.endpoint);
}
