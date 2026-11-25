"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { sidebarRowClass } from "@/components/shell/sidebar-styles";
import { SearchInput } from "@/components/ui/search-input";
import { EYEBROW } from "@/styles/tokens";

import { filterGroups, type SettingsGroup } from "./groups";

/**
 * The settings rail (lg and up): a search box, then the groups as links with an icon each. It
 * matches the main sidebar (owner, 2026-11-25): the full height of the window beside it, the same
 * card padding, row and heading styles, and the search kept at the top while the groups scroll
 * under it with the sidebar's fade. The active page has aria-current and the selected-row look. A
 * group with no match is not rendered.
 */
export function SettingsRail({ slug, groups }: { slug: string; groups: SettingsGroup[] }) {
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const shown = filterGroups(groups, query);
  return (
    <aside className="sticky top-[var(--banner-h,0px)] hidden h-[calc(100dvh-var(--banner-h,0px))] w-64 shrink-0 self-start p-4 pe-0 lg:block xl:w-72">
      <nav aria-label="Settings" className="flex h-full min-h-0 flex-col rounded-xl bg-panel px-2 py-3">
        <div className="px-1">
          <SearchInput
            label="Find a setting"
            placeholder="Find a setting"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="-mx-1 mt-1 min-h-0 flex-1 overflow-y-auto px-1 pb-4 [mask-image:linear-gradient(to_bottom,black_calc(100%-1rem),transparent)] [scrollbar-width:thin]">
          {shown.length === 0 ? (
            <p role="status" className="px-3.5 py-3 text-sm text-fg-secondary">
              No settings match
            </p>
          ) : (
            shown.map((group) => (
              <section key={group.id} aria-labelledby={`settings-group-${group.id}`} className="mt-3">
                <div className="mb-1 px-3.5">
                  <h2 id={`settings-group-${group.id}`} className={EYEBROW}>
                    {group.label}
                  </h2>
                  {group.hint ? <p className="mt-0.5 text-xs text-fg-secondary">{group.hint}</p> : null}
                </div>
                <ul className="flex flex-col gap-0.5">
                  {group.items.map((item) => {
                    const href = `/w/${slug}/settings/${item.segment}`;
                    const active = pathname === href || pathname.startsWith(`${href}/`);
                    return (
                      <li key={item.segment}>
                        <Link
                          href={href as Route}
                          aria-current={active ? "page" : undefined}
                          className={sidebarRowClass({ active })}
                        >
                          <item.icon className="size-4 shrink-0" aria-hidden />
                          <span className="min-w-0 truncate">{item.label}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))
          )}
        </div>
      </nav>
    </aside>
  );
}
