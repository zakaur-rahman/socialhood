"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { WorkspaceSummary } from "@/lib/api/types";

const WorkspaceContext = createContext<WorkspaceSummary | null>(null);

/** The workspace from the URL slug, resolved by the (app)/w/[slug] layout. */
export function WorkspaceProvider({ value, children }: { value: WorkspaceSummary; children: ReactNode }) {
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useCurrentWorkspace(): WorkspaceSummary {
  const workspace = useContext(WorkspaceContext);
  if (!workspace) throw new Error("useCurrentWorkspace must be used inside a workspace route");
  return workspace;
}
