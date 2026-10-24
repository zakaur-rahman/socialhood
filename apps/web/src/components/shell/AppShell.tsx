"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

import type { Route } from "next";

import { AskButton, AskRoot } from "@/components/agent/AskPanel";
import { ThemedUserButton } from "@/components/auth/ThemedClerk";
import { UpgradeDialog } from "@/components/billing/UpgradeDialog";
import { creditsUpgrade } from "@/components/billing/upgrade-requests";
import { useOpenPortal } from "@/components/billing/use-billing-actions";
import { PushSignOutCleanup } from "@/components/push/PushSignOutCleanup";
import { ServiceWorkerRegistrar } from "@/components/push/ServiceWorkerRegistrar";
import { useUpgradeDialog, type UpgradeRequest } from "@/lib/api/provider";
import {
  exhaustedAiCredits,
  keys,
  useBilling,
  useCommentCounts,
  useInboxCounts,
  useMe,
  useSocialAccounts,
  useUpdateWorkspace,
  useWorkspaces,
} from "@/lib/api/queries";
import type { BillingState, Plan, Role, SocialAccount } from "@/lib/api/types";
import { resetAllSet } from "@/components/home/checklist-state";
import { aiCreditsExhausted, reconnectBanner } from "@/lib/copy";
import { useReconnecting } from "@/lib/realtime/status";
import { toastError } from "@/lib/toast-error";
import { useStoredString } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AppSidebar } from "./AppSidebar";
import { BannerSlot, billingBanners, type Banner } from "./BannerSlot";
import { MobileNav } from "./MobileNav";
import { ShellFrame, useSidebarState } from "./ShellFrame";
import { NotificationsButton } from "./NotificationsButton";
import { BILLING_HREF, pageTitle } from "./nav";
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
  const upgradeDialog = useUpgradeDialog();
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
    ...creditBanners(billing.data, workspace.role, upgradeDialog.open),
    ...banners,
  ];
  const counts = useInboxCounts(workspace.id);
  const commentCounts = useCommentCounts(workspace.id);
  const workspaces = useWorkspaces(); // already loaded by the workspace layout
  const reconnecting = useReconnecting();
  const pathname = usePathname();
  const sidebar = useSidebarState(pathname, workspace.slug);
  const updateWorkspace = useUpdateWorkspace(workspace.id);
  const showChecklist = () => {
    resetAllSet(workspace.id);
    updateWorkspace.mutate({ checklist_dismissed: false }, { onError: (error) => toastError(error) });
  };

  const shared = {
    workspace,
    workspaces: workspaces.data,
    userName: me.data?.name ?? null,
    userEmail: me.data?.email ?? null,
    account: <ThemedUserButton />,
    unreadCount: counts.data?.unread ?? 0,
    commentsCount: commentCounts.data?.needs_reply ?? 0,
    credits: creditsUsage(billing.data, billing.isPending),
    reconnecting,
    // UI-058: the setup checklist comes back from the workspace menu (those who can change the workspace).
    onShowChecklist: workspace.role === "agent" ? undefined : showChecklist,
  };

  return (
    <ShellFrame
      topBar={
        <MobileNav
          {...shared}
          title={pageTitle(pathname, workspace.slug)}
          notifications={<NotificationsButton collapsed={false} />}
          ask={<AskButton variant="topbar" />}
        />
      }
      sidebar={
        <AppSidebar
          {...shared}
          collapsed={sidebar.collapsed}
          onToggleCollapsed={sidebar.toggle}
          notifications={<NotificationsButton collapsed={sidebar.collapsed} />}
          ask={<AskButton variant="sidebar" collapsed={sidebar.collapsed} />}
        />
      }
      overlays={
        <>
          {/* FR-AGT-01: Ask Social Hood on every page, with its Ctrl/⌘ K shortcut. */}
          <AskRoot />
          {/* F-15: any 402 opens the upgrade dialog (lib/api/provider.tsx). */}
          <UpgradeDialog />
          {/* TR-FE-09: the push service worker (production builds) and this device's subscription. */}
          <ServiceWorkerRegistrar />
          {/* Signing out removes this browser's push first, so a shared device stops getting alerts. */}
          <PushSignOutCleanup />
        </>
      }
    >
      <BannerSlot banners={allBanners} />
      {children}
    </ShellFrame>
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
export function creditBanners(
  billing: BillingState | undefined,
  role: Role,
  /** Upgrade opens the upgrade dialog, like every Upgrade (UI-063). */
  openUpgrade: (request: UpgradeRequest) => void,
  now?: Date,
): Banner[] {
  const meter = exhaustedAiCredits(billing);
  if (!meter || meter.limit === null || meter.limit === undefined) return [];
  const { used, limit } = meter;
  return [
    {
      id: "ai-credits",
      tone: "warning",
      message: aiCreditsExhausted(limit, meter.period_end, now),
      action: role === "agent" ? undefined : { label: "Upgrade", onClick: () => openUpgrade(creditsUpgrade(used, limit)) },
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
