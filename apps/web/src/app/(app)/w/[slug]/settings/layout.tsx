"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { SETTINGS_SECTIONS } from "@/components/settings/sections";
import { useCurrentWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";

/**
 * UX-SCR-07: the settings tabs, each visible to the roles it was before (C-066). The active tab
 * has an underline and aria-current; on phones the row scrolls sideways and fades at its trailing
 * edge, so the tabs past it read as more to scroll to (UI-ISS-058). The end padding lets the last
 * tab scroll clear of the fade, and the scroll padding stops a tab reached with Tab short of it.
 * The hairline sits on a wrapper, outside the mask, so it doesn't fade; the row overlaps it by 1 px
 * and the active underline covers it. Focus is the global outline, inset because the row clips
 * (DESIGN_SYSTEM §8.3).
 */
export default function SettingsLayout({ children }: { children: ReactNode }) {
  const { slug, role } = useCurrentWorkspace();
  const pathname = usePathname();
  return (
    <div>
      <div className="mx-auto w-full max-w-[1200px] px-4 pt-4 md:px-6 md:pt-6">
        <div className="border-b border-line">
          <nav aria-label="Settings" className="mask-fade-x -mb-px flex gap-1 overflow-x-auto pe-4 scroll-pe-4">
            {SETTINGS_SECTIONS.filter((section) => section.roles.includes(role)).map((section) => {
              const href = `/w/${slug}/settings/${section.segment}`;
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={section.segment}
                  href={href as Route}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex min-h-11 shrink-0 items-center rounded-t-md border-b-2 px-3 text-sm font-medium whitespace-nowrap focus-visible:-outline-offset-2",
                    active
                      ? "border-brand text-fg"
                      : "border-transparent text-fg-secondary hover:border-line-strong hover:text-fg",
                  )}
                >
                  {section.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
      {children}
    </div>
  );
}
