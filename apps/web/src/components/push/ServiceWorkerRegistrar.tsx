"use client";

import { useEffect } from "react";

import { useApi } from "@/lib/api/provider";
import "@/lib/push/install"; // starts listening for beforeinstallprompt with the app's first code
import { syncPushSubscription } from "@/lib/push/sync";

/**
 * TR-FE-09: registers the push service worker once the signed-in app loads (production builds
 * only) and keeps this device's subscription registered with the API. Renders nothing.
 */
export function ServiceWorkerRegistrar() {
  const api = useApi();
  useEffect(() => {
    syncPushSubscription(api).catch(() => {
      // Push stays as it was; Settings → Notifications shows the device's state.
    });
  }, [api]);
  return null;
}
