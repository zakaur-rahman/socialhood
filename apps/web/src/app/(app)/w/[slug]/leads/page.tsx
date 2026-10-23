import type { Metadata } from "next";

import { LeadsPage } from "@/components/leads/LeadsPage";

export const metadata: Metadata = { title: "Leads" };

/** GR-18: the leads view, contacts sorted by lead stage. */
export default function LeadsRoute() {
  return <LeadsPage />;
}
