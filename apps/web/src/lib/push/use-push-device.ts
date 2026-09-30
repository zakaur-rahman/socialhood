"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { ApiError } from "@/lib/api/errors";
import { usePushConfig, useRegisterPush, useUnregisterPush } from "@/lib/api/queries";
import { errorMessage } from "@/lib/copy";

import { defaultPushBrowser, subscriptionBody, type PushBrowser } from "./browser";
import { base64UrlToBytes, deviceSupport, sameKey, type Platform } from "./support";

/**
 * UX-SCR-07: the device's push state. Not supported; not installed on iPhone (push needs the Home
 * Screen app); unavailable (the API has no VAPID keys, or this build has no service worker);
 * blocked in the browser's settings; off; on.
 */
export type PushDeviceState =
  | { kind: "checking" }
  | { kind: "unsupported" }
  | { kind: "ios-install" }
  /** "server": the API has no VAPID keys; "build": a development build without the worker. */
  | { kind: "unavailable"; reason: "server" | "build" }
  | { kind: "denied"; platform: Platform; standalone: boolean }
  | { kind: "off" }
  | { kind: "on" };

const noop = () => () => {};

/** True after hydration: browser APIs are read only on the client. */
function useIsClient(): boolean {
  return useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
}

function pushFailure(error: unknown): string {
  if (error instanceof ApiError) return errorMessage(error);
  if (error instanceof DOMException && error.name === "NotAllowedError") {
    return "Notifications are blocked for Social Hood in this browser.";
  }
  return "Notifications couldn't be turned on on this device. Try again.";
}

/**
 * This device's push subscription (F-19, TR-FE-09): turn on asks for permission inside the click,
 * subscribes with the VAPID key from GET /v1/push/config and registers it with the API; turn off
 * removes it from the API and unsubscribes.
 */
export function usePushDevice(browser: PushBrowser = defaultPushBrowser) {
  const isClient = useIsClient();
  const env = useMemo(() => (isClient ? browser.environment() : null), [isClient, browser]);
  // The answer to the prompt, once asked; until then the browser's current permission.
  const [answered, setAnswered] = useState<NotificationPermission | null>(null);
  const permission = answered ?? env?.permission ?? "default";
  const support = env ? deviceSupport(env) : null;
  const enabled = isClient && browser.enabled();
  const config = usePushConfig(support === "supported" && enabled);
  const register = useRegisterPush();
  const unregister = useUnregisterPush();
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (support !== "supported" || !enabled) return;
    let cancelled = false;
    void (async () => {
      try {
        const registration = await browser.registration();
        const subscription = registration ? await registration.pushManager.getSubscription() : null;
        if (!cancelled) setSubscribed(Boolean(subscription));
      } catch {
        if (!cancelled) setSubscribed(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [browser, support, enabled]);

  const vapidKey = config.data?.enabled ? (config.data.vapid_public_key ?? null) : null;

  let state: PushDeviceState;
  if (!env || support === null) state = { kind: "checking" };
  else if (support === "ios-install") state = { kind: "ios-install" };
  else if (support === "unsupported") state = { kind: "unsupported" };
  else if (!enabled) state = { kind: "unavailable", reason: "build" };
  else if (config.isPending) state = { kind: "checking" };
  else if (!vapidKey) state = { kind: "unavailable", reason: "server" };
  else if (permission === "denied") state = { kind: "denied", platform: env.platform, standalone: env.standalone };
  else if (subscribed === null) state = { kind: "checking" };
  else state = subscribed && permission === "granted" ? { kind: "on" } : { kind: "off" };

  /** Call from the click: the permission prompt needs the user's gesture. */
  const turnOn = async () => {
    if (!vapidKey) return;
    setError(null);
    setBusy(true);
    try {
      const answer = await browser.requestPermission();
      setAnswered(answer);
      if (answer !== "granted") {
        if (answer === "default") setError("Notifications weren't allowed. Turn on again and choose Allow.");
        return;
      }
      const registration = await browser.registration();
      if (!registration) throw new Error("service worker unavailable");
      let subscription = await registration.pushManager.getSubscription();
      if (subscription && !sameKey(subscription.options?.applicationServerKey, vapidKey)) {
        await subscription.unsubscribe();
        subscription = null;
      }
      subscription ??= await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlToBytes(vapidKey),
      });
      try {
        await register.mutateAsync(subscriptionBody(subscription, navigator.userAgent));
      } catch (failure) {
        await subscription.unsubscribe().catch(() => false);
        throw failure;
      }
      setSubscribed(true);
    } catch (failure) {
      setError(pushFailure(failure));
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    setError(null);
    setBusy(true);
    try {
      const registration = await browser.registration();
      const subscription = registration ? await registration.pushManager.getSubscription() : null;
      if (subscription) {
        // The API also drops an endpoint the push service reports gone, so a failure here is fine.
        await unregister.mutateAsync(subscription.endpoint).catch(() => undefined);
        await subscription.unsubscribe();
      }
      setSubscribed(false);
    } catch (failure) {
      setError(pushFailure(failure));
    } finally {
      setBusy(false);
    }
  };

  return { state, busy, error, turnOn, turnOff };
}

/**
 * F-19: whether to offer "Get alerts on your phone" on this device: push could work here (or
 * will, once the iPhone app is on the Home Screen) and isn't on yet. Null while checking.
 */
export function usePushOffer(browser: PushBrowser = defaultPushBrowser): boolean | null {
  const isClient = useIsClient();
  const [offer, setOffer] = useState<boolean | null>(null);
  useEffect(() => {
    if (!isClient) return;
    let cancelled = false;
    const settle = (value: boolean) => {
      if (!cancelled) setOffer(value);
    };
    void (async () => {
      try {
        const env = browser.environment();
        const support = deviceSupport(env);
        if (support === "ios-install") return settle(true);
        if (support !== "supported" || !browser.enabled() || env.permission === "denied") return settle(false);
        if (env.permission !== "granted") return settle(true);
        const registration = await browser.registration();
        const subscription = registration ? await registration.pushManager.getSubscription() : null;
        settle(!subscription);
      } catch {
        settle(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isClient, browser]);
  return offer;
}
