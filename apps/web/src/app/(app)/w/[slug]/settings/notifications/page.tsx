import type { Metadata } from "next";

import { NotificationSettingsPage } from "@/components/push/NotificationSettingsPage";

export const metadata: Metadata = { title: "Notification settings" };

/** UX-SCR-07 Notifications (T8.6): every member's own digest and push settings. */
export default function NotificationSettingsRoute() {
  return <NotificationSettingsPage />;
}
