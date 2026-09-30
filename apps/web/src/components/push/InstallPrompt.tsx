"use client";

import { Download, Share, SquarePlus, X } from "lucide-react";
import { useMemo, useSyncExternalStore, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { useInstallPrompt } from "@/lib/push/install";
import { readEnvironment, type PushEnvironment } from "@/lib/push/support";
import { useStoredFlag } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";

const noop = () => () => {};

/** This browser's platform and whether the app is already installed; null before hydration. */
export function useInstallEnvironment(): PushEnvironment | null {
  const isClient = useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
  return useMemo(() => (isClient ? readEnvironment(window) : null), [isClient]);
}

/** F-19 on iPhone: the two steps to add the app to the Home Screen, where push works. */
export function InstallSteps({ className }: { className?: string }) {
  return (
    <ol className={cn("space-y-2 text-sm", className)} aria-label="Add Social Hood to your Home Screen">
      <li className="flex items-start gap-2.5">
        <span className="grid size-6 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-semibold">1</span>
        <span className="pt-0.5">
          Tap <Share className="inline size-4 align-[-3px] text-brand-fg" aria-label="Share" /> Share in Safari&apos;s
          toolbar.
        </span>
      </li>
      <li className="flex items-start gap-2.5">
        <span className="grid size-6 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-semibold">2</span>
        <span className="pt-0.5">
          Choose <SquarePlus className="inline size-4 align-[-3px] text-brand-fg" aria-hidden /> Add to Home Screen, then
          open Social Hood from your Home Screen.
        </span>
      </li>
    </ol>
  );
}

/**
 * FR-NOT-03: install the app. Where the browser offers it (Chrome, Edge), Install shows its
 * prompt; on iPhone the Add to Home Screen steps. It hides once the app is installed and, when
 * dismissed, stays dismissed in this browser. `action` (for example "Turn on alerts") shows
 * whenever the card does; with `always`, the card shows with just the action where installing
 * isn't possible or needed.
 */
export function InstallPrompt({
  storageKey,
  title,
  body,
  includeIos = true,
  always = false,
  action,
  className,
}: {
  storageKey: string;
  title: string;
  body: string;
  includeIos?: boolean;
  always?: boolean;
  action?: ReactNode;
  className?: string;
}) {
  const env = useInstallEnvironment();
  const { available, install } = useInstallPrompt();
  const [dismissed, setDismissed] = useStoredFlag(storageKey);

  if (!env || dismissed) return null;
  const installed = env.standalone;
  const native = available && !installed;
  const ios = includeIos && env.platform === "ios" && !installed;
  if (!native && !ios && !always) return null;

  return (
    <section
      aria-label={title}
      className={cn("relative rounded-xl border border-brand-line bg-brand-soft p-4 pr-12", className)}
    >
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => setDismissed(true)}
        className="absolute top-2 right-2 grid size-10 place-items-center rounded-md text-fg-secondary hover:bg-white/10 hover:text-fg md:size-8"
      >
        <X className="size-4" aria-hidden />
      </button>
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-sm text-fg-secondary">{body}</p>
      {ios ? <InstallSteps className="mt-3" /> : null}
      {native || action ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {native ? (
            <Button
              className="bg-brand-gradient min-h-10 text-white md:min-h-8"
              onClick={() => {
                void install().then((accepted) => (accepted ? setDismissed(true) : undefined));
              }}
            >
              <Download aria-hidden /> Install app
            </Button>
          ) : null}
          {action}
        </div>
      ) : null}
    </section>
  );
}
