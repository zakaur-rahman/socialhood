import type { Metadata } from "next";

import { SchedulePage } from "@/components/schedule/SchedulePage";

export const metadata: Metadata = { title: "Schedule" };

/** UX-SCR-04: the content calendar. The composer lives at ./[id] (UX-SCR-13). */
export default function ScheduleRoute() {
  return <SchedulePage />;
}
