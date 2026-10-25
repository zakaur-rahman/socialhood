"use client";

import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { useCurrentWorkspace } from "@/lib/workspace";

/** Products are for owners and admins (GR-31); agents never see the nav item, and a direct link explains. */
export default function ProductsLayout({ children }: { children: ReactNode }) {
  const workspace = useCurrentWorkspace();
  if (workspace.role === "agent") {
    return (
      <EmptyState
        className="flex-1"
        title="Products are for owners and admins"
        body="Ask an owner or admin of this workspace to add what you sell."
        action={
          <Link href={`/w/${workspace.slug}/home` as Route} className="text-sm text-brand-fg underline-offset-4 hover:underline">
            Go to Home
          </Link>
        }
      />
    );
  }
  return children;
}
