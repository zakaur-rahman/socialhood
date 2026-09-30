"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import type { Role } from "@/lib/api/types";
import { useCurrentWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";

const EVERYONE: readonly Role[] = ["owner", "admin", "agent"];

// UX-SCR-07 sections in the spec's order, then Agent.
const SECTIONS: readonly { segment: string; label: string; roles: readonly Role[] }[] = [
  { segment: "connections", label: "Connections", roles: EVERYONE },
  { segment: "ai", label: "AI", roles: EVERYONE },
  { segment: "workspace", label: "Workspace", roles: EVERYONE },
  // T8.6: every member's own digest and push settings.
  { segment: "notifications", label: "Notifications", roles: EVERYONE },
  // §3.1: billing is the owner's (admins see it read-only, C-048's Upgrade leads there).
  { segment: "billing", label: "Billing", roles: ["owner", "admin"] },
  // agent-architecture.html §12: Settings → Agent, with the run history (FR-AGT-07).
  { segment: "agent", label: "Agent", roles: EVERYONE },
];

export default function SettingsLayout({ children }: { children: ReactNode }) {
  const { slug, role } = useCurrentWorkspace();
  const pathname = usePathname();
  return (
    <div>
      <nav aria-label="Settings" className="mx-auto flex w-full max-w-[1200px] gap-1 overflow-x-auto px-4 pt-4 md:px-6 md:pt-6">
        {SECTIONS.filter((section) => section.roles.includes(role)).map((section) => {
          const href = `/w/${slug}/settings/${section.segment}`;
          const active = pathname === href;
          return (
            <Link
              key={section.segment}
              href={href as Route}
              aria-current={active ? "page" : undefined}
              className={cn(
                "inline-flex min-h-10 shrink-0 items-center rounded-lg px-3 py-1.5 text-sm font-medium md:min-h-0",
                active ? "bg-white/10 text-fg" : "text-fg-secondary hover:bg-white/5 hover:text-fg",
              )}
            >
              {section.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
