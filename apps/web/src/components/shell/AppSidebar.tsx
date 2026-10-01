"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Route } from "next";
import { LifeBuoy, PanelLeftClose, PanelLeftOpen, Sparkles } from "lucide-react";
import { useId, type ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Role } from "@/lib/api/types";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { cn } from "@/lib/utils";

import { SETTINGS_NAV, activeSegment, navGroupsFor, type NavGroup, type NavItem } from "./nav";
import { COLLAPSE_SHORTCUT_ARIA, shortcutHint, useCollapseShortcut, useModifierKey } from "./shortcuts";
import { KBD_CLASS, sidebarIconClass, sidebarRowClass } from "./sidebar-styles";
import { UsageCard } from "./UsageCard";
import { usageView, type CreditsUsage } from "./usage";
import { WorkspaceMenu, type SidebarWorkspace } from "./WorkspaceMenu";

export type { SidebarWorkspace };

type Props = {
  workspace: SidebarWorkspace;
  /** The member's workspaces, for the switcher; until they load, the current one alone. */
  workspaces?: readonly SidebarWorkspace[];
  collapsed: boolean;
  /** Collapse or expand; also bound to Ctrl/⌘ [. Absent where the sidebar cannot expand. */
  onToggleCollapsed?: () => void;
  /** Unread conversations (FR-INB-04). */
  unreadCount?: number;
  /** Comments waiting for a reply (GET …/comments/counts). */
  commentsCount?: number;
  userName?: string | null;
  userEmail?: string | null;
  /** The AI credits meter from the billing state (usage.ts). */
  credits?: CreditsUsage;
  /** The event stream has been down for a while (lib/realtime/status). */
  reconnecting?: boolean;
  /** Clerk's UserButton in the app; a stand-in in tests. */
  account?: ReactNode;
  /** The notifications bell (UX-SH-04). */
  notifications?: ReactNode;
  /** Ask Social Hood's button (FR-AGT-01), under the header; the card around it is drawn here. */
  ask?: ReactNode;
  /** Called when a link is followed, so the mobile drawer can close. */
  onNavigate?: () => void;
  className?: string;
};

const ROLE_LABEL: Record<Role, string> = { owner: "Owner", admin: "Admin", agent: "Agent" };

type Badge = { count: number; label: string };

/**
 * UX-SH-01: the floating sidebar card, expanded (232 px) or collapsed to icons (64 px). Top to
 * bottom: workspace menu, Ask Social Hood, grouped navigation, then Notifications, Settings, Help
 * and Collapse, the AI credits meter, a notice while live updates are reconnecting, and the
 * account card.
 */
export function AppSidebar({
  workspace,
  workspaces,
  collapsed,
  onToggleCollapsed,
  unreadCount = 0,
  commentsCount = 0,
  userName,
  userEmail,
  credits,
  reconnecting = false,
  account,
  notifications,
  ask,
  onNavigate,
  className,
}: Props) {
  const pathname = usePathname();
  const active = activeSegment(pathname, workspace.slug);
  const modifier = useModifierKey();
  useCollapseShortcut(onToggleCollapsed);

  const badges: Record<string, Badge> = {
    inbox: { count: unreadCount, label: "unread" },
    comments: { count: commentsCount, label: commentsCount === 1 ? "needs a reply" : "need a reply" },
  };
  const collapseHint = shortcutHint(modifier, "[");

  return (
    <nav
      aria-label="Main"
      data-collapsed={collapsed}
      className={cn(
        "relative flex h-full flex-col rounded-xl border border-line bg-panel py-3",
        collapsed ? "w-16 items-center px-2" : "w-[232px] px-2.5",
        className,
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-xl bg-repeat opacity-5"
        style={{ backgroundImage: "url(/grain.jpg)" }}
      />

      <div className={cn("relative w-full", collapsed && "flex justify-center")}>
        <WorkspaceMenu workspace={workspace} workspaces={workspaces} collapsed={collapsed} onNavigate={onNavigate} />
      </div>

      {ask ? <AskCard ask={ask} collapsed={collapsed} hint={shortcutHint(modifier, "K")} /> : null}

      {/* The sections scroll on short screens: the padding leaves room for focus rings, and the
          bottom fades while more is below (the fade falls on empty space otherwise). */}
      <div className="relative -mx-1 mt-3 min-h-0 w-[calc(100%+0.5rem)] flex-1 overflow-y-auto px-1 pb-4 [mask-image:linear-gradient(to_bottom,black_calc(100%-1rem),transparent)] [scrollbar-width:thin]">
        {navGroupsFor(workspace.role).map((group) => (
          <NavSection key={group.key} group={group} collapsed={collapsed}>
            {group.items.map((item) => (
              <li key={item.key} className={cn(collapsed && "flex justify-center")}>
                <SidebarLink
                  item={item}
                  href={item.href(workspace.slug)}
                  active={active === item.segment}
                  collapsed={collapsed}
                  badge={badges[item.key]}
                  onNavigate={onNavigate}
                />
              </li>
            ))}
          </NavSection>
        ))}
      </div>

      <div
        className={cn(
          "relative mt-2 flex w-full flex-col gap-0.5 border-t border-line-subtle pt-2",
          collapsed && "items-center",
        )}
      >
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
            className={sidebarRowClass({ collapsed })}
          >
            <LifeBuoy className={sidebarIconClass()} aria-hidden />
            {collapsed ? null : <span>Help</span>}
          </a>
        </WithTooltip>
        {onToggleCollapsed ? (
          <WithTooltip label={`Expand sidebar (${collapseHint})`} enabled={collapsed}>
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-keyshortcuts={COLLAPSE_SHORTCUT_ARIA}
              className={sidebarRowClass({ collapsed })}
            >
              {collapsed ? (
                <PanelLeftOpen className={sidebarIconClass()} aria-hidden />
              ) : (
                <>
                  <PanelLeftClose className={sidebarIconClass()} aria-hidden />
                  <span>Collapse</span>
                  <kbd className={cn(KBD_CLASS, "ml-auto")}>{collapseHint}</kbd>
                </>
              )}
            </button>
          </WithTooltip>
        ) : null}
      </div>

      <UsageCard
        view={usageView(credits, workspace.role)}
        collapsed={collapsed}
        slug={workspace.slug}
        onNavigate={onNavigate}
      />

      {reconnecting ? <ReconnectingNotice collapsed={collapsed} /> : null}

      <div
        className={cn(
          "relative mt-2 flex w-full items-center gap-2.5 rounded-lg border border-line bg-white/5 p-2",
          collapsed && "justify-center border-0 bg-transparent p-0",
        )}
      >
        {account}
        {collapsed ? null : (
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{userName ?? "Account"}</p>
            <p className="truncate text-xs text-fg-secondary">{userEmail || ROLE_LABEL[workspace.role]}</p>
          </div>
        )}
      </div>
    </nav>
  );
}

/**
 * Ask Social Hood as a card: icon tile (with the AI tag), name, "Your business assistant" and the
 * shortcut. The button itself comes from components/agent and keeps its behaviour and name; here
 * it is stretched, transparent, over the card, so the whole card opens it and shows its focus.
 * Collapsed, the button is shown as it is: an icon with a tooltip.
 */
function AskCard({ ask, collapsed, hint }: { ask: ReactNode; collapsed: boolean; hint: string }) {
  if (collapsed) return <div className="relative mt-2 flex w-full justify-center">{ask}</div>;
  return (
    <div
      data-testid="ask-card"
      className={cn(
        "relative mt-3 flex w-full items-center gap-2.5 rounded-xl border border-brand-line bg-brand-soft p-2",
        "hover:border-brand/60 hover:bg-brand/20 motion-safe:transition-[color,background-color,border-color]",
        "has-[button:focus-visible]:outline-2 has-[button:focus-visible]:outline-offset-2 has-[button:focus-visible]:outline-brand",
      )}
    >
      <span aria-hidden className="bg-brand-gradient relative grid size-8 shrink-0 place-items-center rounded-lg text-white">
        <Sparkles className="size-4" />
        <span className="absolute -right-1.5 -bottom-1 rounded-[4px] bg-panel px-[3px] text-[9px] leading-3 font-bold text-brand-fg ring-1 ring-brand-line">
          AI
        </span>
      </span>
      <span aria-hidden className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="min-w-0 flex-1 truncate text-[13px] leading-5 font-semibold text-fg">Ask Social Hood</span>
          <kbd className={KBD_CLASS}>{hint}</kbd>
        </span>
        <span className="block truncate text-xs leading-4 text-fg-secondary">Your business assistant</span>
      </span>
      <div className="absolute inset-0 [&_button]:absolute [&_button]:inset-0 [&_button]:size-full [&_button]:cursor-pointer [&_button]:rounded-xl [&_button]:opacity-0 [&_button]:outline-none">
        {ask}
      </div>
    </div>
  );
}

function NavSection({ group, collapsed, children }: { group: NavGroup; collapsed: boolean; children: ReactNode }) {
  const id = useId();
  const list = <ul className="flex flex-col gap-0.5">{children}</ul>;
  if (!group.label) return list;
  return (
    <div role="group" aria-labelledby={id} className={collapsed ? "mt-2" : "mt-3"}>
      {collapsed ? (
        <>
          <div aria-hidden className="mx-auto mb-2 h-px w-6 bg-line" />
          <span id={id} className="sr-only">
            {group.label}
          </span>
        </>
      ) : (
        <p id={id} className="mb-1 px-3 text-[11px] leading-4 font-semibold tracking-[0.08em] text-fg-secondary uppercase">
          {group.label}
        </p>
      )}
      {list}
    </div>
  );
}

/** The pill caps at 99+; the rail's corner badge, at 9+, so it never covers the icon. */
function badgeText(count: number, cap: number): string {
  return count > cap ? `${cap}+` : String(count);
}

function SidebarLink({
  item,
  href,
  active,
  collapsed,
  badge,
  onNavigate,
}: {
  item: NavItem;
  href: Route;
  active: boolean;
  collapsed: boolean;
  badge?: Badge;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const count = badge && badge.count > 0 ? badgeText(badge.count, 99) : null;
  // The count is part of the link's name ("Inbox, 3 unread"); the pill itself is decoration.
  const name = count ? `${item.label}, ${count} ${badge?.label}` : item.label;
  const shown = badge && collapsed ? badgeText(badge.count, 9) : count;
  return (
    <WithTooltip label={item.label} enabled={collapsed}>
      <Link
        href={href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        aria-label={collapsed || count ? name : undefined}
        className={sidebarRowClass({ active, collapsed })}
      >
        <Icon className={sidebarIconClass(active)} aria-hidden />
        {collapsed ? null : <span className="min-w-0 flex-1 truncate">{item.label}</span>}
        {count ? (
          <span
            aria-hidden
            data-testid={`${item.key}-badge`}
            className={cn(
              "bg-brand-gradient grid shrink-0 place-items-center rounded-full font-medium text-white tabular-nums",
              collapsed
                ? "absolute top-0.5 right-0.5 h-4 min-w-4 px-1 text-[10px] leading-none ring-2 ring-panel"
                : "h-5 min-w-5 px-1.5 text-xs",
            )}
          >
            {shown}
          </span>
        ) : null}
      </Link>
    </WithTooltip>
  );
}

/** Live updates dropped and have not come back yet: a pill (a dot, collapsed) until they do. */
function ReconnectingNotice({ collapsed }: { collapsed: boolean }) {
  const dot = (
    <span className="relative flex size-2 shrink-0" aria-hidden>
      <span className="absolute inline-flex size-full rounded-full bg-warning opacity-75 motion-safe:animate-ping" />
      <span className="relative inline-flex size-2 rounded-full bg-warning" />
    </span>
  );
  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span role="status" aria-label="Reconnecting…" className="relative mt-2 grid size-10 place-items-center">
            {dot}
          </span>
        </TooltipTrigger>
        <TooltipContent side="right">Reconnecting… Live updates are paused.</TooltipContent>
      </Tooltip>
    );
  }
  return (
    <div
      role="status"
      title="Live updates are paused until the connection is back."
      className="relative mt-2 flex items-center gap-2 self-start rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning"
    >
      {dot}
      Reconnecting…
    </div>
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
