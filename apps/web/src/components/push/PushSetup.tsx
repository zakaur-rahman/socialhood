"use client";

import { BellOff, BellRing, Smartphone } from "lucide-react";
import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { defaultPushBrowser, type PushBrowser } from "@/lib/push/browser";
import type { Platform } from "@/lib/push/support";
import { usePushDevice, type PushDeviceState } from "@/lib/push/use-push-device";

import { InstallSteps } from "./InstallPrompt";

/** How to allow notifications again once they were blocked, per platform. */
export function reenableSteps(platform: Platform, standalone: boolean): string {
  if (platform === "ios") {
    return "Open the Settings app, tap Notifications, then Social Hood, and turn on Allow Notifications.";
  }
  if (platform === "android") {
    return standalone
      ? "Touch and hold the Social Hood icon, tap App info, then Notifications, and allow them."
      : "Tap the icon to the left of the address bar, then Permissions, and allow Notifications.";
  }
  return "Click the icon to the left of the address bar, allow Notifications, then reload this page.";
}

const ON_COPY = "This device gets the alerts you choose below.";
const OFF_COPY = "Get alerts on this device when a conversation needs you, a new lead writes, a reply window is closing or an account needs attention.";

function Notice({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-hover text-fg-secondary" aria-hidden>
        {icon}
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="text-sm font-medium">{title}</p>
        {children}
      </div>
    </div>
  );
}

function StateView({
  state,
  busy,
  onToggle,
}: {
  state: PushDeviceState;
  busy: boolean;
  onToggle: (on: boolean) => void;
}) {
  switch (state.kind) {
    case "checking":
      return (
        <div className="space-y-2" aria-busy="true" aria-label="Checking this device">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-3 w-72 max-w-full" />
        </div>
      );
    case "ios-install":
      return (
        <Notice icon={<Smartphone className="size-4" />} title="Add Social Hood to your Home Screen first">
          <p className="text-sm text-fg-secondary">
            On iPhone, notifications work in the Home Screen app (iOS 16.4 or later). Then open this page there to turn
            them on.
          </p>
          <InstallSteps className="pt-1" />
        </Notice>
      );
    case "unsupported":
      return (
        <Notice icon={<BellOff className="size-4" />} title="This browser can't show notifications from Social Hood">
          <p className="text-sm text-fg-secondary">
            Use Chrome on Android or a computer, or on iPhone add Social Hood to your Home Screen (iOS 16.4 or later).
          </p>
        </Notice>
      );
    case "unavailable":
      return (
        <Notice icon={<BellOff className="size-4" />} title="Phone notifications aren't available right now">
          <p className="text-sm text-fg-secondary">
            {state.reason === "build"
              ? "Push runs in production builds. To try it under next dev, set NEXT_PUBLIC_ENABLE_SW=1."
              : "You'll still see every notification in the app."}
          </p>
        </Notice>
      );
    case "denied":
      return (
        <Notice icon={<BellOff className="size-4" />} title="Notifications are blocked for Social Hood">
          <p className="text-sm text-fg-secondary">{reenableSteps(state.platform, state.standalone)}</p>
        </Notice>
      );
    case "off":
    case "on": {
      const on = state.kind === "on";
      return (
        <div className="flex min-h-10 items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={
                on
                  ? "mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand-fg"
                  : "mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-hover text-fg-secondary"
              }
              aria-hidden
            >
              {on ? <BellRing className="size-4" /> : <BellOff className="size-4" />}
            </span>
            <div className="min-w-0">
              <label htmlFor="push-device" className="text-sm font-medium">
                Notifications on this device
              </label>
              <p id="push-device-hint" className="text-sm text-fg-secondary">
                {on ? ON_COPY : OFF_COPY}
              </p>
            </div>
          </div>
          <Switch
            id="push-device"
            checked={on}
            disabled={busy}
            aria-describedby="push-device-hint"
            aria-busy={busy || undefined}
            onCheckedChange={onToggle}
            className="mt-1.5"
          />
        </div>
      );
    }
  }
}

/**
 * UX-SCR-07, F-19: this device's push notifications. It shows what's possible here (not
 * supported, iPhone not installed, blocked, off or on) and turns push on only from the member's
 * click: the permission prompt, the subscription with the API's VAPID key, and POST
 * /v1/me/push-subscriptions. Turning it off removes the subscription.
 */
export function PushSetup({ browser = defaultPushBrowser }: { browser?: PushBrowser }) {
  const push = usePushDevice(browser);
  return (
    <div className="space-y-3" data-push-state={push.state.kind}>
      <StateView
        state={push.state}
        busy={push.busy}
        onToggle={(on) => {
          // Straight from the click: Safari only shows the prompt during the user's gesture.
          void (on ? push.turnOn() : push.turnOff());
        }}
      />
      {push.error ? (
        <p role="alert" className="text-sm text-danger-fg">
          {push.error}
        </p>
      ) : null}
    </div>
  );
}
