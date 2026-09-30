/**
 * What this browser can do for push (FR-NOT-03, TR-FE-09). Web push needs a service worker, the
 * Push API and notifications, over HTTPS. On iPhone and iPad they exist only in an app added to
 * the Home Screen (iOS 16.4+), so a Safari tab is "install first", not "unsupported".
 */

export type Platform = "ios" | "android" | "desktop";

export type PushEnvironment = {
  platform: Platform;
  /** Opened from the home screen (display-mode standalone, or iOS's navigator.standalone). */
  standalone: boolean;
  /** serviceWorker, PushManager and Notification all exist, in a secure context. */
  pushApis: boolean;
  permission: NotificationPermission | "unsupported";
};

export type DeviceSupport = "supported" | "ios-install" | "unsupported";

type NavigatorLike = { userAgent: string; platform?: string; maxTouchPoints?: number; standalone?: boolean };

export function detectPlatform(nav: NavigatorLike): Platform {
  const ua = nav.userAgent;
  // iPadOS 13+ reports itself as a Mac; touch points tell them apart.
  if (/iPhone|iPad|iPod/.test(ua) || (nav.platform === "MacIntel" && (nav.maxTouchPoints ?? 0) > 1)) return "ios";
  if (/Android/i.test(ua)) return "android";
  return "desktop";
}

export function readEnvironment(win: Window = window): PushEnvironment {
  const nav = win.navigator as Navigator & { standalone?: boolean };
  const standalone =
    nav.standalone === true ||
    Boolean(win.matchMedia?.("(display-mode: standalone)").matches) ||
    Boolean(win.matchMedia?.("(display-mode: fullscreen)").matches);
  const notifications = (win as unknown as { Notification?: { permission: NotificationPermission } }).Notification;
  const pushApis = win.isSecureContext !== false && "serviceWorker" in nav && "PushManager" in win && Boolean(notifications);
  return {
    platform: detectPlatform(nav),
    standalone,
    pushApis,
    permission: notifications ? notifications.permission : "unsupported",
  };
}

/** Push works here; or on iPhone, once the app is on the Home Screen; or not at all. */
export function deviceSupport(env: PushEnvironment): DeviceSupport {
  if (env.pushApis) return "supported";
  if (env.platform === "ios" && !env.standalone) return "ios-install";
  return "unsupported";
}

/** The VAPID key the API sends (base64url) as the bytes PushManager.subscribe takes. */
export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

/** Whether a subscription was made with this VAPID key (a rotated key needs a new one). */
export function sameKey(current: ArrayBuffer | null | undefined, vapidKey: string): boolean {
  if (!current) return true; // browsers that don't expose it: assume it matches
  const expected = base64UrlToBytes(vapidKey);
  const actual = new Uint8Array(current);
  if (actual.length !== expected.length) return false;
  return actual.every((byte, i) => byte === expected[i]);
}
