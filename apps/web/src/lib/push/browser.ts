/**
 * The browser side of push (TR-FE-09), behind one small interface so PushSetup can be tested
 * without a real service worker. public/sw.js shows the notifications; this registers it and
 * manages this device's PushSubscription.
 */
import { readEnvironment, type PushEnvironment } from "./support";

export const SERVICE_WORKER_URL = "/sw.js";

/**
 * The worker is registered only in production builds (or with NEXT_PUBLIC_ENABLE_SW=1 to try push
 * locally), so the Next dev server never runs behind a service worker.
 */
export function serviceWorkerEnabled(): boolean {
  return process.env.NODE_ENV === "production" || process.env.NEXT_PUBLIC_ENABLE_SW === "1";
}

export type PushRegistration = {
  pushManager: Pick<PushManager, "getSubscription" | "subscribe">;
};

export type PushBrowser = {
  environment: () => PushEnvironment;
  /** Whether the service worker may be registered in this build. */
  enabled: () => boolean;
  /** The registration of /sw.js, registering it when needed; null when it can't be. */
  registration: () => Promise<PushRegistration | null>;
  /** Must run inside the click that asked for it (Safari requires a user gesture). */
  requestPermission: () => Promise<NotificationPermission>;
};

let registering: Promise<ServiceWorkerRegistration | null> | null = null;

/** Register /sw.js once per page (scope "/", never served from the HTTP cache). */
export function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === "undefined" || !serviceWorkerEnabled() || !("serviceWorker" in navigator)) {
    return Promise.resolve(null);
  }
  registering ??= navigator.serviceWorker
    .register(SERVICE_WORKER_URL, { scope: "/", updateViaCache: "none" })
    .catch(() => {
      registering = null;
      return null;
    });
  return registering;
}

export const defaultPushBrowser: PushBrowser = {
  environment: () => readEnvironment(window),
  enabled: serviceWorkerEnabled,
  registration: async () => {
    const registration = await registerServiceWorker();
    if (!registration) return null;
    // Subscribing needs an active worker; ready resolves once it is.
    return navigator.serviceWorker.ready;
  },
  requestPermission: () => Notification.requestPermission(),
};

/** PushSubscription.toJSON() as the API takes it (C-049), with the user agent as the device name. */
export function subscriptionBody(subscription: PushSubscription, userAgent: string) {
  const json = subscription.toJSON();
  return {
    endpoint: json.endpoint ?? subscription.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
    user_agent: userAgent.slice(0, 500),
  };
}
