"use client";

import { UserButton } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

import type { Route } from "next";

import { AskButton, AskRoot } from "@/components/agent/AskPanel";
import { UpgradeDialog } from "@/components/billing/UpgradeDialog";
import { useOpenPortal } from "@/components/billing/use-billing-actions";
import { ServiceWorkerRegistrar } from "@/components/push/ServiceWorkerRegistrar";
import {
  exhaustedAiCredits,
  keys,
  useBilling,
  useCommentCounts,
  useInboxCounts,
  useMe,
  useSocialAccounts,
  useWorkspaces,
} from "@/lib/api/queries";
import type { BillingState, Plan, Role, SocialAccount } from "@/lib/api/types";
import { aiCreditsExhausted, reconnectBanner } from "@/lib/copy";
import { useReconnecting } from "@/lib/realtime/status";
import { useMediaQuery, useStoredFlag, useStoredString } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AppSidebar } from "./AppSidebar";
import { BannerSlot, billingBanners, type Banner } from "./BannerSlot";
import { MobileNav } from "./MobileNav";
import { NotificationsButton } from "./NotificationsButton";
import { activeSegment, BILLING_HREF, pageTitle } from "./nav";
import { creditsUsage } from "./usage";

/**
 * The signed-in frame: sidebar on desktop (collapsed below 1024 px, 1280 px in the inbox;
 * remembered per browser above it), top bar and drawer on phones (UX-SH-01…04). The Inbox
 * item carries the unread count (FR-INB-04) and Comments the comments waiting for a reply, both
 * kept fresh by real-time events.
 */
export function AppShell({ children, banners = [] }: { children: ReactNode; banners?: Banner[] }) {
  const workspace = useCurrentWorkspace();
  const me = useMe();
  const accounts = useSocialAccounts(workspace.id);
  const billing = useBilling(workspace.id);
  const portal = useOpenPortal(workspace.id);
  const [dismissedTrial, setDismissedTrial] = useStoredString<string>("socialhood:trial-reminder-dismissed", "");
  usePlanChanges(workspace.id, workspace.plan, billing.data?.plan);
  const allBanners = [
    ...billingBanners(billing.data, {
      role: workspace.role,
      timeZone: workspace.timezone,
      billingHref: BILLING_HREF(workspace.slug),
      onManageBilling: portal.open,
      managing: portal.pending,
      dismissedTrial,
      onDismissTrial: setDismissedTrial,
    }),
    ...accountBanners(accounts.data ?? [], workspace.slug),
    ...creditBanners(billing.data, workspace.slug, workspace.role),
    ...banners,
  ];
  const counts = useInboxCounts(workspace.id);
  const commentCounts = useCommentCounts(workspace.id);
  const workspaces = useWorkspaces(); // already loaded by the workspace layout
  const reconnecting = useReconnecting();
  const pathname = usePathname();
  // UX-INB-01: the inbox needs the room, so the sidebar collapses below 1280 px there.
  const inbox = activeSegment(pathname, workspace.slug) === "inbox";
  const wide = useMediaQuery(inbox ? "(min-width: 1280px)" : "(min-width: 1024px)");
  const [collapsedPreference, setCollapsedPreference] = useStoredFlag("socialhood:sidebar-collapsed");
  const collapsed = !wide || collapsedPreference;

  const shared = {
    workspace,
    workspaces: workspaces.data,
    userName: me.data?.name ?? null,
    userEmail: me.data?.email ?? null,
    account: <UserButton />,
    unreadCount: counts.data?.unread ?? 0,
    commentsCount: commentCounts.data?.needs_reply ?? 0,
    credits: creditsUsage(billing.data, billing.isPending),
    reconnecting,
  };

  return (
    <div className="min-h-dvh md:flex">
      <MobileNav
        {...shared}
        title={pageTitle(pathname, workspace.slug)}
        notifications={<NotificationsButton collapsed={false} />}
        ask={<AskButton variant="topbar" />}
      />
      <aside className="sticky top-0 hidden h-dvh shrink-0 p-4 pr-0 md:block">
        <AppSidebar
          {...shared}
          collapsed={collapsed}
          onToggleCollapsed={wide ? () => setCollapsedPreference(!collapsedPreference) : undefined}
          notifications={<NotificationsButton collapsed={collapsed} />}
          ask={<AskButton variant="sidebar" collapsed={collapsed} />}
        />
      </aside>
      <main className="min-w-0 flex-1">
        <BannerSlot banners={allBanners} />
        {children}
      </main>
      {/* FR-AGT-01: Ask Social Hood on every page, with its Ctrl/⌘ K shortcut. */}
      <AskRoot />
      {/* F-15: any 402 opens the upgrade dialog (lib/api/provider.tsx). */}
      <UpgradeDialog />
      {/* TR-FE-09: the push service worker (production builds) and this device's subscription. */}
      <ServiceWorkerRegistrar />
    </div>
  );
}

/**
 * A plan change (usage.updated, C-049) reaches the rest of the app: the sidebar's plan badge
 * reads GET /v1/workspaces, and a downgrade changes accounts and automations (FR-BIL-07), so
 * the workspace's queries refetch once when the billing plan differs from what was seen.
 */
function usePlanChanges(wid: string, workspacePlan: Plan, billingPlan: Plan | undefined) {
  const queryClient = useQueryClient();
  const seen = useRef<Plan | undefined>(undefined);
  useEffect(() => {
    if (!billingPlan) return;
    const previous = seen.current;
    seen.current = billingPlan;
    if (previous && previous !== billingPlan) {
      void queryClient.invalidateQueries({ queryKey: ["w", wid] });
      void queryClient.invalidateQueries({ queryKey: keys.workspaces });
    } else if (!previous && billingPlan !== workspacePlan) {
      void queryClient.invalidateQueries({ queryKey: keys.workspaces });
    }
  }, [queryClient, wid, workspacePlan, billingPlan]);
}

/**
 * FR-AI-05: when the AI credits are used up, analysis, suggestions and auto replies stop and a
 * banner says when they reset, with an upgrade link for those who can upgrade. Messaging goes on.
 */
export function creditBanners(billing: BillingState | undefined, slug: string, role: Role, now?: Date): Banner[] {
  const meter = exhaustedAiCredits(billing);
  if (!meter || meter.limit === null || meter.limit === undefined) return [];
  return [
    {
      id: "ai-credits",
      tone: "warning",
      message: aiCreditsExhausted(meter.limit, meter.period_end, now),
      action: role === "agent" ? undefined : { label: "Upgrade", href: BILLING_HREF(slug) },
    },
  ];
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
