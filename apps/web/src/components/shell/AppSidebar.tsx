"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Route } from "next";
import { ChevronLeft, LifeBuoy, Sparkles } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Role } from "@/lib/api/types";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

import { SETTINGS_NAV, activeSegment, navGroupsFor, type NavGroup, type NavItem } from "./nav";
import { COLLAPSE_SHORTCUT_ARIA, shortcutHint, useCollapseShortcut, useModifierKey } from "./shortcuts";
import { useCollapsedTooltip } from "./use-collapsed-tooltip";
import { KBD_CLASS, sidebarFadeClass, sidebarIconClass, sidebarLabelClass, sidebarRowClass } from "./sidebar-styles";
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
  /** "Show setup checklist" in the workspace menu (UI-058); absent where the user can't change the workspace. */
  onShowChecklist?: () => void;
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
  onShowChecklist,
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
  // Transitions switch on after the first paint, so a restored state shows at once and only later
  // changes (the button, Ctrl/⌘ [, the inbox's auto-collapse, a resize across the breakpoint) animate.
  // (A DOM attribute, not state: no extra render, and React never resets it.)
  const navRef = useRef<HTMLElement>(null);
  useEffect(() => {
    navRef.current?.setAttribute("data-ready", "true");
  }, []);

  return (
    <nav
      ref={navRef}
      aria-label="Main"
      data-collapsed={collapsed}
      data-ready="false"
      className={cn(
        "group/sb relative h-full rounded-xl border border-line glass-pane",
        collapsed ? "w-16" : "w-[232px]",
        "motion-safe:data-[ready=true]:transition-[width] motion-safe:data-[ready=true]:duration-slow motion-safe:data-[ready=true]:ease-standard",
        className,
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-xl bg-repeat opacity-(--grain-opacity)"
        style={{ backgroundImage: "url(/grain.jpg)" }}
      />

      {/* Owner, 2026-10-25: the toggle is an icon on the card's right edge, centred, half over the
          border; the label and the Ctrl/⌘ [ shortcut are in its tooltip. z-40 keeps it above the
          page's sticky headers, which it overlaps by half its width. */}
      {onToggleCollapsed ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-keyshortcuts={COLLAPSE_SHORTCUT_ARIA}
              className="absolute top-1/2 -right-3 z-40 flex size-6 -translate-y-1/2 items-center justify-center rounded-full border border-line glass-float text-fg-secondary shadow-glass transition-colors duration-fast hover:border-line-strong hover:text-fg"
            >
              <ChevronLeft
                className={cn(
                  "size-3.5 motion-safe:group-data-[ready=true]/sb:transition-transform motion-safe:group-data-[ready=true]/sb:duration-slow motion-safe:group-data-[ready=true]/sb:ease-standard",
                  collapsed && "rotate-180",
                )}
                aria-hidden
              />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {collapsed ? "Expand sidebar" : "Collapse sidebar"} ({collapseHint})
          </TooltipContent>
        </Tooltip>
      ) : null}

      {/* Everything else lives in a clipping box (the toggle above must overlap the edge, so the nav
          itself cannot clip): the collapsed card is the expanded one cut off at 64 px. */}
      <div className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-xl px-2 py-3">
      <div className="relative w-full">
        <WorkspaceMenu
          workspace={workspace}
          workspaces={workspaces}
          collapsed={collapsed}
          onNavigate={onNavigate}
          onShowChecklist={onShowChecklist}
        />
      </div>

      {ask ? <AskCard ask={ask} collapsed={collapsed} hint={shortcutHint(modifier, "K")} /> : null}

      {/* The sections scroll on short screens: the padding leaves room for focus rings, and the
          bottom fades while more is below (the fade falls on empty space otherwise). */}
      <div className="relative -mx-1 mt-3 min-h-0 w-[calc(100%+0.5rem)] flex-1 overflow-x-hidden overflow-y-auto px-1 pb-4 [mask-image:linear-gradient(to_bottom,black_calc(100%-1rem),transparent)] [scrollbar-width:thin]">
        {navGroupsFor(workspace.role).map((group) => (
          <NavSection key={group.key} group={group} collapsed={collapsed}>
            {group.items.map((item) => (
              <li key={item.key}>
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

      <div className="relative mt-2 flex w-full flex-col gap-0.5 border-t border-line-subtle pt-2">
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
            className={sidebarRowClass()}
          >
            <LifeBuoy className={sidebarIconClass()} aria-hidden />
            <span aria-hidden={collapsed} className={sidebarLabelClass(collapsed)}>
              Help
            </span>
          </a>
        </WithTooltip>
      </div>

      <UsageCard view={usageView(credits, workspace.role)} collapsed={collapsed} />

      {reconnecting ? <ReconnectingNotice collapsed={collapsed} /> : null}

      <div
        className={cn(
          "relative mt-2 flex w-full items-center gap-2.5 overflow-hidden rounded-lg border p-1.5 motion-safe:group-data-[ready=true]/sb:transition-[background-color,border-color] motion-safe:group-data-[ready=true]/sb:duration-slow motion-safe:group-data-[ready=true]/sb:ease-standard",
          collapsed ? "border-transparent bg-transparent" : "border-line bg-hover",
        )}
      >
        <div className="shrink-0">{account}</div>
        <div inert={collapsed} aria-hidden={collapsed} className={cn("min-w-0 flex-1", sidebarFadeClass(!collapsed))}>
          <p className="truncate text-sm font-medium">{userName ?? "Account"}</p>
          <p className="truncate text-xs text-fg-secondary">{userEmail || ROLE_LABEL[workspace.role]}</p>
        </div>
      </div>
      </div>
    </nav>
  );
}

/**
 * Ask Social Hood as a card: icon tile (with the AI tag), name, "Your AI assistant" and the
 * shortcut. The button itself comes from components/agent and keeps its behaviour and name; here
 * it is stretched, transparent, over the card, so the whole card opens it and shows its focus.
 * Collapsed, the button is shown as it is: an icon with a tooltip.
 */
function AskCard({ ask, collapsed, hint }: { ask: ReactNode; collapsed: boolean; hint: string }) {
  return (
    <div
      data-testid="ask-card"
      className={cn(
        "relative mt-3 flex w-full items-center gap-2.5 overflow-hidden rounded-xl border border-brand-line bg-brand-soft p-1.5",
        "hover:bg-brand-soft-hover motion-safe:transition-[color,background-color]",
        "has-[button:focus-visible]:outline-2 has-[button:focus-visible]:outline-offset-2 has-[button:focus-visible]:outline-brand",
      )}
    >
      <span aria-hidden className="bg-brand-gradient relative grid size-8 shrink-0 place-items-center rounded-lg text-on-brand">
        <Sparkles className="size-4" />
        <span className="absolute -right-1 -bottom-1 rounded-sm bg-panel px-0.5 text-2xs leading-3 font-semibold text-brand-fg ring-1 ring-brand-line">
          AI
        </span>
      </span>
      <span aria-hidden className={cn("min-w-0 flex-1", sidebarFadeClass(!collapsed))}>
        {/* The name gets its own line, so it is never cut ("Ask Social Ho…"); the shortcut sits with
            the subtitle. */}
        <span className="block truncate text-sm font-semibold whitespace-nowrap text-fg">Ask Social Hood</span>
        <span className="flex items-center gap-1.5">
          <span className="min-w-0 flex-1 truncate text-xs leading-4 whitespace-nowrap text-fg-secondary">Your AI assistant</span>
          <kbd className={KBD_CLASS}>{hint}</kbd>
        </span>
      </span>
      {/* The same card in both states: the button over it keeps its behaviour, its name and its
          tooltip (collapsed, the card is the icon tile alone). */}
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
    <div role="group" aria-labelledby={id} className="mt-3">
      {/* Same height in both states, so no row moves: expanded, the heading; collapsed, it fades
          out and a short divider fades in at the same place. The heading still names the group. */}
      <div className="relative mb-1">
        <p id={id} aria-hidden={collapsed} className={cn(EYEBROW, "px-3.5 whitespace-nowrap", sidebarFadeClass(!collapsed))}>
          {group.label}
        </p>
        <div
          aria-hidden
          className={cn("absolute inset-x-0 top-1/2 mx-auto h-px w-6 bg-line", sidebarFadeClass(collapsed, { slide: false }))}
        />
      </div>
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
        className={sidebarRowClass({ active })}
      >
        <Icon className={sidebarIconClass(active)} aria-hidden />
        <span aria-hidden={collapsed} className={sidebarLabelClass(collapsed)}>
          {item.label}
        </span>
        {count ? (
          <Badge
            tone="count"
            size={collapsed ? "sm" : "md"}
            aria-hidden
            data-testid={`${item.key}-badge`}
            // Collapsed, the count sits on the icon corner: a smaller compound (RG-01, DS-3).
            className={cn(collapsed && "absolute top-0.5 right-0.5 h-4 min-w-4 px-1 leading-none ring-2 ring-panel")}
          >
            {shown}
          </Badge>
        ) : null}
      </Link>
    </WithTooltip>
  );
}

/**
 * Live updates dropped and have not come back yet: a pill until they do. It is a row like the
 * others (the dot sits in the icon column), and its words fade out when collapsed.
 */
function ReconnectingNotice({ collapsed }: { collapsed: boolean }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          role="status"
          aria-label="Reconnecting…"
          className="relative mt-2 flex h-8 w-full items-center gap-3 overflow-hidden rounded-full bg-warning-soft px-3.5 text-xs font-medium whitespace-nowrap text-warning"
        >
          <span className="relative grid size-4.5 shrink-0 place-items-center" aria-hidden>
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full rounded-full bg-warning opacity-75 motion-safe:animate-ping" />
              <span className="relative inline-flex size-2 rounded-full bg-warning" />
            </span>
          </span>
          <span aria-hidden={collapsed} className={sidebarLabelClass(collapsed)}>
            Reconnecting…
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="right">
        {collapsed ? "Reconnecting… Live updates are paused." : "Live updates are paused until the connection is back."}
      </TooltipContent>
    </Tooltip>
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
  // Always wrapped, so the row is never remounted when the sidebar collapses (its text keeps
  // animating); the tooltip's content exists only while collapsed, and it opens only from a hover
  // after collapsing (useCollapsedTooltip).
  const tooltip = useCollapsedTooltip(enabled);
  return (
    <Tooltip {...tooltip}>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      {enabled ? <TooltipContent side="right">{label}</TooltipContent> : null}
    </Tooltip>
  );
}
