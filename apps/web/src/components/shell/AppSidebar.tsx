"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Route } from "next";
import { LifeBuoy, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import type { ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Plan, Role } from "@/lib/api/types";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { cn } from "@/lib/utils";

import { BILLING_HREF, SETTINGS_NAV, activeSegment, navFor, type NavItem } from "./nav";

export type SidebarWorkspace = { name: string; slug: string; plan: Plan; role: Role };

type Props = {
  workspace: SidebarWorkspace;
  collapsed: boolean;
  onToggleCollapsed?: () => void;
  unreadCount?: number;
  userName?: string | null;
  /** Clerk's UserButton in the app; a stand-in in tests. */
  account?: ReactNode;
  /** The notifications bell (UX-SH-04). */
  notifications?: ReactNode;
  /** Called when a link is followed, so the mobile drawer can close. */
  onNavigate?: () => void;
  className?: string;
};

const PLAN_LABEL: Record<Plan, string> = { free: "Free", pro: "Pro", max: "Max" };

/** UX-SH-01: the floating sidebar card, expanded (200 px) or collapsed to icons (64 px). */
export function AppSidebar({
  workspace,
  collapsed,
  onToggleCollapsed,
  unreadCount = 0,
  userName,
  account,
  notifications,
  onNavigate,
  className,
}: Props) {
  const pathname = usePathname();
  const active = activeSegment(pathname, workspace.slug);

  return (
    <nav
      aria-label="Main"
      data-collapsed={collapsed}
      className={cn(
        "relative flex h-full flex-col gap-1 rounded-xl border border-line bg-panel p-3",
        collapsed ? "w-16 items-center px-2" : "w-[200px]",
        className,
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-xl bg-repeat opacity-5"
        style={{ backgroundImage: "url(/grain.jpg)" }}
      />

      <div className={cn("relative mb-4 flex items-center gap-2.5", collapsed && "justify-center")}>
        <span className="bg-shell-gradient size-9 shrink-0 rounded-xl" aria-hidden />
        {collapsed ? (
          <span className="sr-only">Social Hood</span>
        ) : (
          <span className="min-w-0">
            <span className="block text-sm font-medium">Social Hood</span>
            <span className="block truncate text-xs text-fg-secondary">{workspace.name}</span>
          </span>
        )}
      </div>

      <ul className="relative flex w-full flex-col gap-1">
        {navFor(workspace.role).map((item) => (
          <li key={item.key}>
            <SidebarLink
              item={item}
              href={item.href(workspace.slug)}
              active={active === item.segment}
              collapsed={collapsed}
              badge={item.key === "inbox" ? unreadCount : 0}
              onNavigate={onNavigate}
            />
          </li>
        ))}
      </ul>

      <div className="flex-1" />

      <div className="relative flex w-full flex-col gap-1">
        {notifications}
        <SidebarLink
          item={SETTINGS_NAV}
          href={SETTINGS_NAV.href(workspace.slug)}
          active={active === SETTINGS_NAV.segment}
          collapsed={collapsed}
          onNavigate={onNavigate}
        />
        <WithTooltip label={`Help: ${SUPPORT_EMAIL}`} enabled={collapsed}>
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            aria-label={collapsed ? "Help" : undefined}
            className={itemClass(false, collapsed)}
          >
            <LifeBuoy className="size-5 shrink-0" aria-hidden />
            {collapsed ? null : <span>Help</span>}
          </a>
        </WithTooltip>
        {onToggleCollapsed ? (
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={itemClass(false, collapsed)}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-5 shrink-0" aria-hidden />
            ) : (
              <>
                <PanelLeftClose className="size-5 shrink-0" aria-hidden />
                <span>Collapse</span>
              </>
            )}
          </button>
        ) : null}
      </div>

      {workspace.plan === "free" && !collapsed ? (
        <Link
          href={BILLING_HREF(workspace.slug)}
          onClick={onNavigate}
          className="bg-shell-gradient relative mt-2 rounded-lg px-3 py-2 text-center text-sm font-medium text-white"
        >
          Upgrade
        </Link>
      ) : null}

      <div
        className={cn(
          "relative mt-2 flex items-center gap-2 rounded-lg border border-line bg-white/5 p-2",
          collapsed && "justify-center border-0 bg-transparent p-0",
        )}
      >
        {account}
        {collapsed ? null : (
          <div className="min-w-0 text-xs">
            <p className="truncate font-medium">{userName ?? "Account"}</p>
            <p className="text-fg-secondary">{PLAN_LABEL[workspace.plan]} plan</p>
          </div>
        )}
      </div>
    </nav>
  );
}

function itemClass(active: boolean, collapsed: boolean): string {
  return cn(
    "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-medium text-fg-secondary hover:bg-white/5 hover:text-fg",
    active && "bg-raised text-fg hover:bg-raised",
    collapsed && "size-10 justify-center px-0 py-0",
  );
}

function SidebarLink({
  item,
  href,
  active,
  collapsed,
  badge = 0,
  onNavigate,
}: {
  item: NavItem;
  href: Route;
  active: boolean;
  collapsed: boolean;
  badge?: number;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const count = badge > 99 ? "99+" : String(badge);
  return (
    <WithTooltip label={item.label} enabled={collapsed}>
      <Link
        href={href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        aria-label={collapsed ? item.label : undefined}
        className={itemClass(active, collapsed)}
      >
        <Icon className={cn("size-5 shrink-0", active && "text-brand-fg")} aria-hidden />
        {collapsed ? null : <span>{item.label}</span>}
        {badge > 0 ? (
          <span
            aria-label={`${count} unread`}
            className={cn(
              "bg-brand-gradient grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-xs text-white tabular-nums",
              collapsed ? "absolute -right-1 -top-1" : "ml-auto",
            )}
          >
            {count}
          </span>
        ) : null}
      </Link>
    </WithTooltip>
  );
}

function WithTooltip({
  label,
  enabled,
  children,
}: {
  label: string;
  enabled: boolean;
  children: ReactNode;
}) {
  if (!enabled) return <>{children}</>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}
