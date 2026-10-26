import type { Route } from "next";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { appUrl } from "@/lib/marketing/site";
import { appLink } from "@/lib/resolve";

export const NOTIFICATION_SETTINGS_LABEL = "Open notification settings";

/**
 * UI-ISS-110: the way back from the unsubscribe page, straight to Settings › Notifications, where
 * the digest turns back on. The page doesn't know the workspace's address, so the link goes
 * through /app, which opens the page in the last used workspace (signing in first if needed), on
 * the app's own host when it has one (C-146).
 */
export function NotificationSettingsLink() {
  return (
    <Link
      href={appUrl(appLink("settings/notifications")) as Route}
      prefetch={false}
      data-slot="button"
      data-variant="secondary"
      data-size="xl"
      className={buttonVariants({ variant: "secondary", size: "xl" })}
    >
      {NOTIFICATION_SETTINGS_LABEL}
    </Link>
  );
}
