"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";

import { AutomationEditor } from "@/components/automations/AutomationEditor";
import { PageSkeleton } from "@/components/states/PageSkeleton";

/** UX-SCR-03. Keyed by id, so no draft state survives a switch between automations. */
export default function AutomationRoute() {
  const { id } = useParams<{ id: string }>();
  return (
    <Suspense fallback={<PageSkeleton />}>
      <AutomationEditor key={id} id={id} />
    </Suspense>
  );
}
