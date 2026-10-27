import type { Metadata } from "next";

import { ActivityPage } from "@/components/activity/ActivityPage";

export const metadata: Metadata = { title: "Activity" };

/** GR-05 Settings › Activity: what automations and sends did, what failed, and what to do. */
export default function ActivityRoute() {
  return <ActivityPage />;
}
