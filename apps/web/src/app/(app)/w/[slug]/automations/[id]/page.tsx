"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";

import { AutomationEditor } from "@/components/automations/AutomationEditor";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { useAutomation } from "@/lib/api/queries";
import { useDocumentTitle } from "@/lib/document-title";
import { useCurrentWorkspace } from "@/lib/workspace";

/** UX-SCR-03. Keyed by id, so no draft state survives a switch between automations. */
export default function AutomationRoute() {
  const { id } = useParams<{ id: string }>();
  return (
    <Suspense fallback={<PageSkeleton />}>
      <AutomationTitle id={id} />
      <AutomationEditor key={id} id={id} />
    </Suspense>
  );
}

/** The tab's title is the automation's name (UI-ISS-061). */
function AutomationTitle({ id }: { id: string }) {
  const workspace = useCurrentWorkspace();
  const automation = useAutomation(workspace.id, id);
  useDocumentTitle(automation.data?.name ?? "Automation");
  return null;
}
