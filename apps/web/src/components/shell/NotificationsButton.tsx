"use client";

import { AlertTriangle, Bell, CircleAlert, Info } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { GetAlertsCard } from "@/components/push/GetAlertsCard";
import { EmptyState } from "@/components/states/EmptyState";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useMarkNotificationsRead, useNotifications } from "@/lib/api/queries";
import type { NotificationItem } from "@/lib/api/types";
import { emptyStates } from "@/lib/copy";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { sidebarIconClass, sidebarRowClass } from "./sidebar-styles";

/** UX-SH-04: the bell opens a 360 px panel of the member's notifications (FR-NOT-01). */
export function NotificationsButton({ collapsed }: { collapsed: boolean }) {
  const workspace = useCurrentWorkspace();
  const notifications = useNotifications(workspace.id);
  const markRead = useMarkNotificationsRead(workspace.id);
  const [open, setOpen] = useState(false);
  const unread = notifications.data?.unread_count ?? 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        className={cn(sidebarRowClass({ collapsed }), "data-[state=open]:bg-pressed data-[state=open]:text-fg")}
      >
        <span className="relative shrink-0">
          <Bell className={sidebarIconClass()} aria-hidden />
          {/* Dots under 12 px are solid brand, not the gradient (DESIGN_SYSTEM §1.9, UI-ISS-055). */}
          {unread > 0 ? (
            <span className="absolute -top-0.5 -right-0.5 size-2 rounded-full bg-brand ring-2 ring-panel" aria-hidden />
          ) : null}
        </span>
        {collapsed ? null : <span>Notifications</span>}
      </PopoverTrigger>
      <PopoverContent side="right" align="end" className="w-90 p-0">
        <NotificationsPanel
          items={notifications.data?.items ?? []}
          unread={unread}
          slug={workspace.slug}
          offer={
            <GetAlertsCard
              items={notifications.data?.items ?? []}
              slug={workspace.slug}
              onNavigate={() => setOpen(false)}
            />
          }
          marking={markRead.isPending}
          onMarkAllRead={() => markRead.mutate({ all: true })}
          onOpen={(item) => {
            if (!item.read_at) markRead.mutate({ ids: [item.id] });
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

const SEVERITY_ICON = {
  critical: { icon: CircleAlert, className: "text-danger" },
  warning: { icon: AlertTriangle, className: "text-warning" },
  info: { icon: Info, className: "text-brand-fg" },
} as const;

export function NotificationsPanel({
  items,
  unread,
  slug,
  marking,
  onMarkAllRead,
  onOpen,
  offer,
  now = new Date(),
}: {
  items: NotificationItem[];
  unread: number;
  slug: string;
  marking: boolean;
  onMarkAllRead: () => void;
  onOpen: (item: NotificationItem) => void;
  /** F-19: "Get alerts on your phone", above the list. */
  offer?: ReactNode;
  now?: Date;
}) {
  return (
    <div>
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <p className="text-sm font-semibold">Notifications</p>
        <Button variant="ghost" size="sm" disabled={unread === 0 || marking} onClick={onMarkAllRead}>
          Mark all read
        </Button>
      </div>
      {offer}
      {items.length === 0 ? (
        <EmptyState title={emptyStates.notifications.title} body={emptyStates.notifications.body} />
      ) : (
        <ul className="max-h-105 overflow-y-auto py-1">
          {items.map((item) => {
            const { icon: Icon, className } = SEVERITY_ICON[item.severity];
            const body = (
              <>
                <Icon className={cn("mt-0.5 size-4 shrink-0", className)} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className={cn("block truncate text-sm", item.read_at ? "font-normal" : "font-semibold")}>
                    {item.title}
                  </span>
                  <span className="block truncate text-xs text-fg-secondary">{item.body}</span>
                </span>
                <span className="shrink-0 text-xs text-fg-secondary">{relativeTime(item.created_at, now)}</span>
                {item.read_at ? null : (
                  <span className="mt-1.5 size-2 shrink-0 rounded-full bg-brand" aria-label="unread" />
                )}
              </>
            );
            const rowClass = "flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-hover";
            return (
              <li key={item.id}>
                {item.link ? (
                  <Link href={`/w/${slug}${item.link}` as Route} className={rowClass} onClick={() => onOpen(item)}>
                    {body}
                  </Link>
                ) : (
                  <button type="button" className={rowClass} onClick={() => onOpen(item)}>
                    {body}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
