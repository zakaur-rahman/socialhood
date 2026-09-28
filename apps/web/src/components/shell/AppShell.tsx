"use client";

import { UserButton } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import type { Route } from "next";

import { useMe, useSocialAccounts } from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { reconnectBanner } from "@/lib/copy";
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
  const accounts = useSocialAccounts(workspace.id);
  const allBanners = [...accountBanners(accounts.data ?? [], workspace.slug), ...banners];
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
        <BannerSlot banners={allBanners} />
        {children}
      </main>
    </div>
  );
}

/** F-05 / FR-CON-04: every account that needs reconnecting gets a banner until it is fixed. */
export function accountBanners(accounts: SocialAccount[], slug: string): Banner[] {
  return accounts
    .filter((account) => account.status === "needs_reconnect")
    .map((account) => ({
      id: `reconnect:${account.id}`,
      tone: "warning" as const,
      message: reconnectBanner(account.username),
      action: { label: "Reconnect", href: `/w/${slug}/settings/connections` as Route },
    }));
}
