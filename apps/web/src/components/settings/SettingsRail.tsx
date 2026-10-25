"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { sidebarRowClass } from "@/components/shell/sidebar-styles";
import { SearchInput } from "@/components/ui/search-input";

import { filterGroups, type SettingsGroup } from "./groups";

/**
 * The settings rail (lg and up): a search box, then the groups as links with an icon each. The
 * active page has aria-current and the sidebar's selected-row look. Sticky beside the page on the
 * card glass; it scrolls itself on a short viewport. A group with no match is not rendered.
 */
export function SettingsRail({ slug, groups }: { slug: string; groups: SettingsGroup[] }) {
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const shown = filterGroups(groups, query);
  return (
    <aside className="sticky top-0 hidden max-h-dvh w-64 shrink-0 self-start p-4 pe-0 lg:block xl:w-72">
      <nav
        aria-label="Settings"
        className="glass-card flex max-h-[calc(100dvh-2rem)] flex-col gap-4 overflow-y-auto rounded-xl border border-line p-3"
      >
        <SearchInput
          label="Find a setting"
          placeholder="Find a setting"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {shown.length === 0 ? (
          <p role="status" className="px-2 py-3 text-sm text-fg-secondary">
            No settings match
          </p>
        ) : (
          shown.map((group) => (
            <section key={group.id} aria-labelledby={`settings-group-${group.id}`} className="space-y-1">
              <div className="px-2">
                <h2
                  id={`settings-group-${group.id}`}
                  className="text-xs font-medium tracking-wide text-fg-secondary uppercase"
                >
                  {group.label}
                </h2>
                {group.hint ? <p className="text-xs text-fg-secondary">{group.hint}</p> : null}
              </div>
              <ul className="space-y-0.5">
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
      </nav>
    </aside>
  );
}
