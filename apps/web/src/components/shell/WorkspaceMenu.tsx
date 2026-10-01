"use client";

import { Check, ChevronsUpDown, Settings } from "lucide-react";
import Link from "next/link";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Plan, Role } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { WORKSPACE_HOME_HREF, WORKSPACE_SETTINGS_HREF } from "./nav";

export type SidebarWorkspace = { name: string; slug: string; plan: Plan; role: Role };

export const PLAN_LABEL: Record<Plan, string> = { free: "Free", pro: "Pro", max: "Max" };

export function PlanBadge({ plan, className }: { plan: Plan; className?: string }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded px-1.5 text-[10px] leading-4 font-semibold",
        plan === "free" ? "bg-hover text-fg-secondary" : "bg-brand-soft text-brand-fg",
        className,
      )}
    >
      {PLAN_LABEL[plan]}
    </span>
  );
}

/** The logo mark: the shell-gradient tile (UX-SH-01). */
export function LogoMark({ className }: { className?: string }) {
  return <span aria-hidden className={cn("bg-shell-gradient size-9 shrink-0 rounded-xl", className)} />;
}

/**
 * The sidebar's header: logo, "Social Hood" with the plan, and the workspace name. It opens a
 * menu to switch between the member's workspaces (GET /v1/workspaces) and to reach workspace
 * settings. Collapsed, it is the logo alone, named by a tooltip.
 */
export function WorkspaceMenu({
  workspace,
  workspaces,
  collapsed,
  onNavigate,
}: {
  workspace: SidebarWorkspace;
  workspaces?: readonly SidebarWorkspace[];
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const others = (workspaces ?? []).filter((w) => w.slug !== workspace.slug);
  const trigger = (
    <DropdownMenuTrigger
      aria-label={`Workspace menu: ${workspace.name}`}
      className={cn(
        "relative flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left hover:bg-white/5 data-[state=open]:bg-white/5 motion-safe:transition-[color,background-color]",
        collapsed && "size-10 justify-center p-0",
      )}
    >
      <LogoMark className={collapsed ? "size-9" : undefined} />
      {collapsed ? null : (
        <>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1.5">
              <span className="truncate text-sm font-semibold">Social Hood</span>
              <PlanBadge plan={workspace.plan} />
            </span>
            <span className="block truncate text-xs text-fg-secondary">{workspace.name}</span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-fg-secondary" aria-hidden />
        </>
      )}
    </DropdownMenuTrigger>
  );

  return (
    <DropdownMenu>
      {collapsed ? (
        <Tooltip>
          <TooltipTrigger asChild>{trigger}</TooltipTrigger>
          <TooltipContent side="right">
            {workspace.name} · {PLAN_LABEL[workspace.plan]}
          </TooltipContent>
        </Tooltip>
      ) : (
        trigger
      )}
      <DropdownMenuContent
        side={collapsed ? "right" : "bottom"}
        align="start"
        className="w-60 border-line bg-panel"
      >
        <DropdownMenuLabel className="text-xs font-medium text-fg-secondary">Workspaces</DropdownMenuLabel>
        <DropdownMenuItem aria-current="true" className="gap-2 py-1.5">
          <span className="min-w-0 flex-1 truncate">{workspace.name}</span>
          <PlanBadge plan={workspace.plan} />
          <Check className="text-brand-fg" aria-hidden />
        </DropdownMenuItem>
        {others.map((other) => (
          <DropdownMenuItem key={other.slug} asChild className="gap-2 py-1.5">
            <Link href={WORKSPACE_HOME_HREF(other.slug)} onClick={onNavigate}>
              <span className="min-w-0 flex-1 truncate">{other.name}</span>
              <PlanBadge plan={other.plan} />
              <span className="size-4" aria-hidden />
            </Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="gap-2 py-1.5">
          <Link href={WORKSPACE_SETTINGS_HREF(workspace.slug)} onClick={onNavigate}>
            <Settings className="text-fg-secondary" aria-hidden />
            Workspace settings
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
