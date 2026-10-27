import type { Metadata } from "next";

import { BusinessHoursPage } from "@/components/hours/BusinessHoursPage";

export const metadata: Metadata = { title: "Business hours" };

/** GR-22: when the workspace is open, the away message and Auto mode's hours. */
export default function BusinessHoursRoute() {
  return <BusinessHoursPage />;
}
