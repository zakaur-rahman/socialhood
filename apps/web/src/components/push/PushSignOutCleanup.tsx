"use client";

import { useClerk } from "@clerk/nextjs";
import { useEffect } from "react";

import { useApi } from "@/lib/api/provider";
import { guardSignOut, removePushSubscription } from "@/lib/push/sign-out";

type SignOutTarget = Parameters<typeof guardSignOut>[0];

/**
 * FR-NOT-03 on shared devices: once Clerk has loaded, its sign-out first removes this browser's
 * push subscription (lib/push/sign-out.ts). The wrap is on Clerk's own instance, the one its
 * UserButton menu calls, so every way of signing out is covered. Renders nothing.
 */
export function PushSignOutCleanup() {
  const api = useApi();
  const clerk = useClerk();
  const loaded = clerk.loaded;
  useEffect(() => {
    if (!loaded) return;
    // useClerk() is a wrapper whose signOut calls the loaded instance's; the UI calls that one.
    const instance =
      (clerk as unknown as { clerkjs?: SignOutTarget | null }).clerkjs ??
      (window as unknown as { Clerk?: SignOutTarget }).Clerk ??
      (clerk as unknown as SignOutTarget);
    return guardSignOut(instance, () => removePushSubscription(api));
  }, [api, clerk, loaded]);
  return null;
}
