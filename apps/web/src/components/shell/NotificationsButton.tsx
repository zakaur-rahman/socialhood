"use client";

import { Bell } from "lucide-react";

import { EmptyState } from "@/components/states/EmptyState";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { emptyStates } from "@/lib/copy";
import { cn } from "@/lib/utils";

/**
 * UX-SH-04: the bell opens a 360 px panel. Notifications themselves arrive in P8 (T8.5); until
 * then the panel shows its empty state.
 */
export function NotificationsButton({ collapsed, unread = 0 }: { collapsed: boolean; unread?: number }) {
  return (
    <Popover>
      <PopoverTrigger
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        className={cn(
          "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-medium text-fg-secondary hover:bg-white/5 hover:text-fg",
          collapsed && "size-10 justify-center px-0 py-0",
        )}
      >
        <Bell className="size-5 shrink-0" aria-hidden />
        {collapsed ? null : <span>Notifications</span>}
        {unread > 0 ? (
          <span className="bg-brand-gradient absolute right-2 top-2 size-2 rounded-full" aria-hidden />
        ) : null}
      </PopoverTrigger>
      <PopoverContent side="right" align="end" className="w-[360px] border-line bg-panel p-0 shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <p className="text-sm font-semibold">Notifications</p>
          <Button variant="ghost" size="sm" disabled>
            Mark all read
          </Button>
        </div>
        <EmptyState title={emptyStates.notifications.title} body={emptyStates.notifications.body} />
      </PopoverContent>
    </Popover>
  );
}
