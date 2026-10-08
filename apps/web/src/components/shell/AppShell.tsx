"use client";

import { UserButton } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

import type { Route } from "next";

import { AskButton, AskRoot } from "@/components/agent/AskPanel";
import { UpgradeDialog } from "@/components/billing/UpgradeDialog";
import { useOpenPortal } from "@/components/billing/use-billing-actions";
import { PushSignOutCleanup } from "@/components/push/PushSignOutCleanup";
import { ServiceWorkerRegistrar } from "@/components/push/ServiceWorkerRegistrar";
import { PageSkeleton } from "@/components/states/PageSkeleton";
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
import { minWidth } from "@/lib/breakpoints";
import { aiCreditsExhausted, reconnectBanner } from "@/lib/copy";
import { useReconnecting } from "@/lib/realtime/status";
import { useMediaQuery, useStoredFlag, useStoredString } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
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
  const sidebar = useSidebarState(pathname, workspace.slug);

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
 * UX-INB-01: the inbox needs the room, so the sidebar collapses below 1280 px there (`xl`; `lg`,
 * 1024 px, elsewhere); above that the choice is remembered per browser. The loading shell uses it
 * too, so the sidebar has its final width before the workspace loads.
 */
function useSidebarState(pathname: string, slug: string) {
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
        className="sr-only rounded-lg bg-brand-strong text-sm font-medium text-on-brand focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:inline-flex focus:min-h-10 focus:items-center focus:px-4"
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
 * GET /v1/workspaces answers.
 */
export function ShellSkeleton() {
  const pathname = usePathname();
  const { slug } = useParams<{ slug: string }>();
  const sidebar = useSidebarState(pathname, slug);
  return (
    <ShellFrame
      topBar={
        <div aria-hidden className="sticky top-0 z-40 flex h-14 items-center border-b border-line bg-panel px-4 md:hidden">
          <span className="bg-shell-gradient size-8 shrink-0 rounded-lg" />
        </div>
      }
      sidebar={
        <div
          aria-hidden
          className={cn("h-full rounded-xl border border-line bg-panel", sidebar.collapsed ? "w-16" : "w-[232px]")}
        />
      }
    >
      <PageSkeleton />
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
