"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell, ShellSkeleton } from "@/components/shell/AppShell";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { useWorkspace, useWorkspaces } from "@/lib/api/queries";
import { useWorkspaceEvents } from "@/lib/realtime/use-workspace-events";
import { WorkspaceProvider } from "@/lib/workspace";

/**
 * TR-FE-01: resolve the slug through GET /v1/workspaces. A slug the user is not a member of
 * renders "Workspace not found" with a link to /app (F-02).
 */
export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  const { slug } = useParams<{ slug: string; id?: string }>();
  const workspaces = useWorkspaces();

  // The shell frame stays put while the workspace loads (UI-ISS-114).
  if (workspaces.isPending) return <ShellSkeleton />;
  if (workspaces.isError) {
    return <ErrorState fullPage error={workspaces.error} onRetry={() => void workspaces.refetch()} />;
  }
  const workspace = workspaces.data.find((w) => w.slug === slug);
  if (!workspace) {
    return (
      <EmptyState
        className="min-h-dvh"
        title="Workspace not found"
        body="It may have been renamed, or you may not be a member of it."
        action={
          <Link href="/app" className="text-sm text-brand-fg underline-offset-4 hover:underline">
            Go to your workspace
          </Link>
        }
      />
    );
  }
  return (
    <WorkspaceProvider value={workspace}>
      <RememberWorkspace id={workspace.id} />
      <WorkspaceEvents id={workspace.id} />
      <AppShell>{children}</AppShell>
    </WorkspaceProvider>
  );
}

/** Opening a workspace records it as the user's last one, so /app returns here (F-02). */
function RememberWorkspace({ id }: { id: string }) {
  useWorkspace(id);
  return null;
}

/** TR-FE-04: one real-time stream per tab, patching the cache for every page below. */
function WorkspaceEvents({ id }: { id: string }) {
  const { id: routeId } = useParams<{ id?: string }>();
  // [id] is a conversation only in the inbox (automations/[id] is an automation).
  const inInbox = usePathname().includes("/inbox/");
  useWorkspaceEvents(id, inInbox ? (routeId ?? null) : null);
  return null;
}
