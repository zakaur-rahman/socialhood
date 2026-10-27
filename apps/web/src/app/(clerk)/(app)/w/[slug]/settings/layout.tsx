"use client";

import { usePathname } from "next/navigation";
import type { Route } from "next";
import type { ReactNode } from "react";

import { BackLink } from "@/components/shell/PageFrame";
import { visibleGroups } from "@/components/settings/groups";
import { SettingsRail } from "@/components/settings/SettingsRail";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * UX-SCR-07: from lg, a grouped rail beside the page (sticky, with a filter box); each page is
 * visible to the roles it was before (C-066). Below lg there is no rail: /settings is a list of
 * the same groups, and a page under it opens with a "Settings" back link. The page header keeps
 * its own sticky behaviour (PageFrame's STICKY_PAGE_HEADER).
 */
export default function SettingsLayout({ children }: { children: ReactNode }) {
  const { slug, role } = useCurrentWorkspace();
  const pathname = usePathname();
  const home = `/w/${slug}/settings`;
  const onHome = pathname === home || pathname === `${home}/`;
  return (
    <div className="lg:flex lg:items-start">
      <SettingsRail slug={slug} groups={visibleGroups(role)} />
      <div className="min-w-0 flex-1">
        {onHome ? null : (
          <div className="px-4 pt-3 md:px-6 lg:hidden">
            <BackLink href={home as Route} label="Settings" />
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
