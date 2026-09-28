"use client";

import { UserButton } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import type { Route } from "next";

import { useInboxCounts, useMe, useSocialAccounts } from "@/lib/api/queries";
import type { SocialAccount } from "@/lib/api/types";
import { reconnectBanner } from "@/lib/copy";
import { useMediaQuery, useStoredFlag } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AppSidebar } from "./AppSidebar";
import { BannerSlot, type Banner } from "./BannerSlot";
import { MobileNav } from "./MobileNav";
import { NotificationsButton } from "./NotificationsButton";
import { activeSegment, pageTitle } from "./nav";

/**
 * The signed-in frame: sidebar on desktop (collapsed below 1024 px, 1280 px in the inbox;
 * remembered per browser above it), top bar and drawer on phones (UX-SH-01…04). The Inbox
 * item carries the unread count (FR-INB-04), kept fresh by real-time events.
 */
export function AppShell({ children, banners = [] }: { children: ReactNode; banners?: Banner[] }) {
  const workspace = useCurrentWorkspace();
  const me = useMe();
  const accounts = useSocialAccounts(workspace.id);
  const allBanners = [...accountBanners(accounts.data ?? [], workspace.slug), ...banners];
  const counts = useInboxCounts(workspace.id);
  const pathname = usePathname();
  // UX-INB-01: the inbox needs the room, so the sidebar collapses below 1280 px there.
  const inbox = activeSegment(pathname, workspace.slug) === "inbox";
  const wide = useMediaQuery(inbox ? "(min-width: 1280px)" : "(min-width: 1024px)");
  const [collapsedPreference, setCollapsedPreference] = useStoredFlag("socialhood:sidebar-collapsed");
  const collapsed = !wide || collapsedPreference;

  const shared = {
    workspace,
    userName: me.data?.name ?? null,
    account: <UserButton />,
    unreadCount: counts.data?.unread ?? 0,
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
