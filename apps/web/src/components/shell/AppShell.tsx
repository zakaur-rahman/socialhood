"use client";

import { UserButton } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useMe } from "@/lib/api/queries";
import { useMediaQuery, useStoredFlag } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AppSidebar } from "./AppSidebar";
import { BannerSlot, type Banner } from "./BannerSlot";
import { MobileNav } from "./MobileNav";
import { NotificationsButton } from "./NotificationsButton";
import { pageTitle } from "./nav";

/**
 * The signed-in frame: sidebar on desktop (collapsed below 1024 px, remembered per browser
 * above it), top bar and drawer on phones (UX-SH-01…04).
 */
export function AppShell({ children, banners = [] }: { children: ReactNode; banners?: Banner[] }) {
  const workspace = useCurrentWorkspace();
  const me = useMe();
  const pathname = usePathname();
  const wide = useMediaQuery("(min-width: 1024px)");
  const [collapsedPreference, setCollapsedPreference] = useStoredFlag("socialhood:sidebar-collapsed");
  const collapsed = !wide || collapsedPreference;

  const shared = {
    workspace,
    userName: me.data?.name ?? null,
    account: <UserButton />,
  };

  return (
    <div className="min-h-dvh md:flex">
      <MobileNav
        {...shared}
        title={pageTitle(pathname, workspace.slug)}
        notifications={<NotificationsButton collapsed={false} />}
      />
      <aside className="sticky top-0 hidden h-dvh shrink-0 p-4 pr-0 md:block">
        <AppSidebar
          {...shared}
          collapsed={collapsed}
          onToggleCollapsed={wide ? () => setCollapsedPreference(!collapsedPreference) : undefined}
          notifications={<NotificationsButton collapsed={collapsed} />}
        />
      </aside>
      <main className="min-w-0 flex-1">
        <BannerSlot banners={banners} />
        {children}
      </main>
    </div>
  );
}
