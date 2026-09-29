import type { Metadata } from "next";

import { AutomationsPage } from "@/components/automations/AutomationsPage";

export const metadata: Metadata = { title: "Automations" };

/** UX-SCR-02. */
export default function AutomationsRoute() {
  return <AutomationsPage />;
}
