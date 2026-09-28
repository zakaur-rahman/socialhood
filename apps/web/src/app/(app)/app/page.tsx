"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { useMe } from "@/lib/api/queries";
import { SUPPORT_EMAIL } from "@/lib/copy";

/**
 * /app resolver (F-01, F-02): GET /v1/me provisions a first-time user, then we go to the last
 * used workspace. It opens Home until the inbox exists (P3); then Home only when no account is
 * connected. If /v1/me fails, show the error with Retry and never bounce back to sign-in.
 */
export default function AppResolverPage() {
  const me = useMe();
  const router = useRouter();

  const target = me.data
    ? (me.data.workspaces.find((w) => w.id === me.data.last_workspace_id) ?? me.data.workspaces[0])
    : undefined;

  useEffect(() => {
    if (target) router.replace(`/w/${target.slug}/home`);
  }, [target, router]);

  if (me.isError) return <ErrorState fullPage error={me.error} onRetry={() => void me.refetch()} />;
  if (me.data && !target) {
    return (
      <EmptyState
        className="min-h-dvh"
        title="No workspace"
        body="Your account isn't in any workspace right now."
        action={
          <a className="text-sm text-brand-fg underline-offset-4 hover:underline" href={`mailto:${SUPPORT_EMAIL}`}>
            Contact support
          </a>
        }
      />
    );
  }
  return <PageSkeleton fullPage />;
}
