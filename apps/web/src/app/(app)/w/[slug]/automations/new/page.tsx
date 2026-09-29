import type { Metadata } from "next";

import { AutomationsPage } from "@/components/automations/AutomationsPage";

export const metadata: Metadata = { title: "New automation" };

/** F-11: New automation opens the template gallery (UX-SCR-11) over the list. */
export default function NewAutomationRoute() {
  return <AutomationsPage openGallery />;
}
