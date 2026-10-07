"use client";

import { useSelectedLayoutSegment } from "next/navigation";
import type { ReactNode } from "react";

import { AutomationsPage } from "@/components/automations/AutomationsPage";

/**
 * UX-SCR-02 and UX-SCR-11: /automations and /automations/new are one screen, the list, with the
 * template gallery open on /new. Rendering it here, once for both routes, keeps it mounted when the
 * gallery (or Ask's draft) closes back to /automations: no remount, so the filters stay and focus
 * goes back where it belongs, while each route keeps its own title.
 */
export default function AutomationsListLayout({ children }: { children: ReactNode }) {
  const segment = useSelectedLayoutSegment();
  return (
    <>
      <AutomationsPage openGallery={segment === "new"} />
      {children}
    </>
  );
}
