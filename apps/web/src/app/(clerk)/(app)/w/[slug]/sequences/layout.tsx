"use client";

import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { useCurrentWorkspace } from "@/lib/workspace";

/** Sequences are for owners and admins (GR-24); a direct link from an agent explains. */
export default function SequencesLayout({ children }: { children: ReactNode }) {
  const workspace = useCurrentWorkspace();
  if (workspace.role === "agent") {
    return (
      <EmptyState
        className="flex-1"
        title="Sequences are for owners and admins"
        body="Ask an owner or admin of this workspace to set them up."
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
