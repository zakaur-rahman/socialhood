import type { Metadata } from "next";
import { Suspense } from "react";

import { WeeklyReportPage } from "@/components/reports/WeeklyReportPage";

export const metadata: Metadata = { title: "Weekly report" };

/** GR-34: the weekly report, one address per week (`?week=YYYY-MM-DD`), for members only. */
export default function ReportsRoute() {
  return (
    // The week is read from the address, which needs a boundary while the page is prerendered.
    <Suspense fallback={null}>
      <WeeklyReportPage />
    </Suspense>
  );
}
