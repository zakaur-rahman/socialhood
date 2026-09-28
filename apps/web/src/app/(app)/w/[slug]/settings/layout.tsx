"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useCurrentWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";

// UX-SCR-07 sections in the spec's order; AI, Notifications and Billing join as they are built.
const SECTIONS = [
  { segment: "connections", label: "Connections" },
  { segment: "workspace", label: "Workspace" },
] as const;

export default function SettingsLayout({ children }: { children: ReactNode }) {
  const { slug } = useCurrentWorkspace();
  const pathname = usePathname();
  return (
    <div>
      <nav aria-label="Settings" className="mx-auto flex w-full max-w-[1200px] gap-1 px-4 pt-4 md:px-6 md:pt-6">
        {SECTIONS.map((section) => {
          const href = `/w/${slug}/settings/${section.segment}`;
          const active = pathname === href;
          return (
            <Link
              key={section.segment}
              href={href as Route}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium",
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
