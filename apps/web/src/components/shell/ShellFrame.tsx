"use client";

import { useParams, usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { PageSkeleton } from "@/components/states/PageSkeleton";
import { minWidth } from "@/lib/breakpoints";
import { useMediaQuery, useStoredFlag } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";

import { activeSegment } from "./nav";

/**
 * UX-INB-01: the inbox needs the room, so the sidebar collapses below 1280 px there (`xl`; `lg`,
 * 1024 px, elsewhere); above that the choice is remembered per browser. The loading shell uses it
 * too, so the sidebar has its final width before the workspace loads.
 */
export function useSidebarState(pathname: string, slug: string) {
  const inbox = activeSegment(pathname, slug) === "inbox";
  // Server value: expanded (desktop). Below md the sidebar is hidden by CSS, so the guess only
  // shows from 768 px, where desktops are the common case. (The shell, its loading skeleton
  // included, mounts in the browser once Clerk has loaded, so today this is a fallback.)
  const wide = useMediaQuery(minWidth(inbox ? "xl" : "lg"), true);
  const [collapsedPreference, setCollapsedPreference] = useStoredFlag("socialhood:sidebar-collapsed");
  return {
    collapsed: !wide || collapsedPreference,
    toggle: wide ? () => setCollapsedPreference(!collapsedPreference) : undefined,
  };
}

/**
 * The shell's frame (UX-SH-01…03, UX-A11Y-01): "Skip to content" first, the phone top bar, the
 * sidebar from 768 px and `<main>`. `<main>` is a full-height flex column: banners sit in its flow,
 * and a full-height frame (the inbox, the Ask page) marks itself `data-shell-fill` and takes the
 * rest with `flex-1 min-h-0`, which caps the shell at the viewport's height, so a banner never
 * pushes the composer off-screen (UI-ISS-020). Unsized text in the app is 14 px (`text-sm`).
 */
export function ShellFrame({
  topBar,
  sidebar,
  overlays,
  children,
}: {
  topBar: ReactNode;
  sidebar: ReactNode;
  overlays?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col has-[[data-shell-fill]]:h-dvh md:flex-row">
      <a
        href="#main"
        className="sr-only rounded-lg bg-brand-strong text-sm font-medium text-on-brand focus:not-sr-only focus:fixed focus:top-3 focus:left-1/2 focus:z-50 focus:-translate-x-1/2 focus:inline-flex focus:min-h-10 focus:items-center focus:px-4"
      >
        Skip to content
      </a>
      {topBar}
      <div className="sticky top-0 hidden h-dvh shrink-0 p-4 pr-0 md:block">{sidebar}</div>
      <main id="main" tabIndex={-1} className="flex min-h-0 min-w-0 flex-1 flex-col text-sm outline-none">
        {children}
      </main>
      {overlays}
    </div>
  );
}

/**
 * The shell while the workspace loads (UI-ISS-114): the same frame, with the phone top bar and the
 * sidebar at their final size, and the page's skeleton in `<main>`, so nothing moves when
 * GET /v1/workspaces answers. The signed-in layout shows it too while the API client loads.
 * The skip link sits at the top centre: at the left it covered the logo (UI-041).
 */
export function ShellSkeleton() {
  const pathname = usePathname();
  // Outside a workspace (/app) there is no slug; the sidebar still gets its final width.
  const { slug } = useParams<{ slug?: string }>();
  const sidebar = useSidebarState(pathname, slug ?? "");
  return (
    <ShellFrame
      topBar={
        <div aria-hidden data-testid="shell-skeleton-topbar" className="sticky top-0 z-40 flex h-14 items-center border-b border-line glass-pane px-4 md:hidden">
          <span className="bg-shell-gradient size-8 shrink-0 rounded-lg" />
        </div>
      }
      sidebar={
        <div
          aria-hidden
          data-testid="shell-skeleton-sidebar"
          className={cn("h-full rounded-xl border border-line glass-pane", sidebar.collapsed ? "w-16" : "w-[232px]")}
        />
      }
    >
      <PageSkeleton />
    </ShellFrame>
  );
}
