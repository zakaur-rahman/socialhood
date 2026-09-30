/**
 * Signing out stops this browser's push (FR-NOT-03, TR-FE-09): on a shared device the next person
 * must not see the previous member's alerts on the lock screen. Before Clerk signs out, the
 * browser's subscription is removed from the API (still signed in, so the call is authorised) and
 * unsubscribed, best effort and never holding sign-out up for more than about 2 s.
 */
import type { Api } from "@/lib/api/client";

import type { PushRegistration } from "./browser";
import { forgetSyncedPush } from "./sync";

/** The longest sign-out waits for the clean-up. */
export const SIGN_OUT_CLEANUP_MS = 2_000;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** The existing registration only: signing out never registers the worker. */
async function existingRegistration(): Promise<PushRegistration | null> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return null;
  return (await navigator.serviceWorker.getRegistration("/")) ?? null;
}

/**
 * DELETE /v1/me/push-subscriptions?endpoint= and PushSubscription.unsubscribe(), side by side
 * (either alone stops the alerts: the API also drops endpoints the push service reports gone).
 * Resolves after both, or after `timeoutMs`, whichever is first; never rejects.
 */
export async function removePushSubscription(
  api: Api,
  {
    timeoutMs = SIGN_OUT_CLEANUP_MS,
    registration = existingRegistration,
  }: { timeoutMs?: number; registration?: () => Promise<PushRegistration | null> } = {},
): Promise<void> {
  forgetSyncedPush();
  const work = (async () => {
    const found = await registration();
    const subscription = found ? await found.pushManager.getSubscription() : null;
    if (!subscription) return;
    await Promise.allSettled([
      api.DELETE("/v1/me/push-subscriptions", { params: { query: { endpoint: subscription.endpoint } } }),
      subscription.unsubscribe(),
    ]);
  })().catch(() => undefined);
  await Promise.race([work, delay(timeoutMs)]);
}

type SignOut = (...args: never[]) => Promise<unknown>;
type SignOutTarget = { signOut: SignOut };

const GUARDED = Symbol.for("socialhood.push-sign-out");

/**
 * Wraps `target.signOut` (Clerk's instance) so `before` runs first. Every sign-out goes through
 * it: UserButton's menu, SignOutButton and useClerk().signOut() all call the instance's method.
 * `before` is capped at `timeoutMs` and its failures are ignored. Returns a function that undoes
 * the wrap.
 */
export function guardSignOut(
  target: SignOutTarget,
  before: () => Promise<void>,
  timeoutMs = SIGN_OUT_CLEANUP_MS,
): () => void {
  const original = target.signOut;
  if ((original as SignOut & { [GUARDED]?: true })[GUARDED]) return () => {};
  const guarded = Object.assign(
    async function guardedSignOut(this: unknown, ...args: never[]) {
      await Promise.race([before().catch(() => undefined), delay(timeoutMs)]);
      return original.apply(target, args);
    },
    { [GUARDED]: true as const },
  );
  target.signOut = guarded;
  return () => {
    if (target.signOut === guarded) target.signOut = original;
  };
}
