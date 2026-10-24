"use client";

import { ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useDocumentTitle } from "@/lib/document-title";
import { useCurrentWorkspace } from "@/lib/workspace";
import { PAGE_TITLE } from "@/styles/tokens";

import { visibleGroups } from "./groups";

/**
 * /settings. Below lg it is the settings home: the groups as tappable rows. From lg the rail
 * is beside the page, so there is nothing to list: after mount, a matchMedia check sends the
 * browser to the first page this role sees. The list is always in the markup (hidden from lg by
 * CSS), so server and client render the same and nothing depends on the window width.
 */
export function SettingsHome() {
  useDocumentTitle("Settings");
  const { slug, role } = useCurrentWorkspace();
  const router = useRouter();
  const groups = visibleGroups(role);
  const first = groups[0]?.items[0]?.segment;

  useEffect(() => {
    if (!first || typeof window.matchMedia !== "function") return;
    const wide = window.matchMedia("(min-width: 1024px)");
    const go = () => {
      if (wide.matches) router.replace(`/w/${slug}/settings/${first}` as Route);
    };
    go();
    wide.addEventListener("change", go);
    return () => wide.removeEventListener("change", go);
  }, [first, router, slug]);

  return (
    <div className="w-full space-y-6 px-4 pt-5 pb-6 md:px-6 md:pt-6 lg:hidden">
      <h1 className={PAGE_TITLE}>Settings</h1>
      {groups.map((group) => (
        <section key={group.id} aria-labelledby={`settings-home-${group.id}`} className="space-y-2">
          <div>
            <h2
              id={`settings-home-${group.id}`}
              className="text-xs font-medium tracking-wide text-fg-secondary uppercase"
            >
              {group.label}
            </h2>
            {group.hint ? <p className="text-xs text-fg-secondary">{group.hint}</p> : null}
          </div>
          <ul className="glass-card divide-y divide-line overflow-hidden rounded-xl border border-line">
            {group.items.map((item) => (
              <li key={item.segment}>
                <Link
                  href={`/w/${slug}/settings/${item.segment}` as Route}
                  className="flex min-h-14 items-center gap-3 px-4 py-2 hover:bg-hover focus-visible:-outline-offset-2"
                >
                  <item.icon className="size-5 shrink-0 text-fg-secondary" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-fg">{item.label}</span>
                    {item.description ? (
                      <span className="block truncate text-xs text-fg-secondary">{item.description}</span>
                    ) : null}
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-fg-secondary" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
