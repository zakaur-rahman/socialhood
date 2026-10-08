"use client";

import type { Route } from "next";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import { useMe, useSocialAccounts } from "@/lib/api/queries";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { resolveDestination } from "@/lib/resolve";

/**
 * /app resolver (F-01, F-02): the last used workspace's inbox, or Home while no account is
 * connected. If /v1/me fails, show the error with Retry and never bounce back to sign-in.
 */
export default function AppResolverPage() {
  return (
    <Suspense fallback={<PageSkeleton fullPage />}>
      <Resolver />
    </Suspense>
  );
}

function Resolver() {
  const me = useMe();
  const router = useRouter();
  const params = useSearchParams();
  const connectError = params.get("error");
  const next = params.get("next"); // a page outside the app asked for (lib/resolve.ts)

  const target = me.data
    ? (me.data.workspaces.find((w) => w.id === me.data.last_workspace_id) ?? me.data.workspaces[0])
    : undefined;
  const accounts = useSocialAccounts(target?.id ?? "", Boolean(target) && connectError !== "state_invalid");
  // Accounts failing to load should not strand the user: Home works without them.
  const destination = target
    ? resolveDestination(target.slug, accounts.isError ? [] : accounts.data, connectError, next)
    : null;

  useEffect(() => {
    if (destination) router.replace(destination as Route);
  }, [destination, router]);

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
