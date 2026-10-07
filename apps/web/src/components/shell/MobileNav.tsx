"use client";

import { Menu } from "lucide-react";
import { useState, type ComponentProps, type ReactNode } from "react";

import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

import { AppSidebar } from "./AppSidebar";
import { STATIC_WHEN_SHORT } from "./sticky-bar";

type Props = Omit<ComponentProps<typeof AppSidebar>, "collapsed" | "onNavigate" | "onToggleCollapsed" | "ask"> & {
  title: string;
  /** Ask Social Hood's button (FR-AGT-01), beside the menu. */
  ask?: ReactNode;
};

/**
 * UX-SH-02: below 768 px, a 56 px top bar with the logo, page title, Ask Social Hood and a menu
 * button. The drawer holds the expanded sidebar; it is closed on load and closes when a link is
 * tapped (v1 opened on load and stayed open). The bar sticks (the page's top scroll padding keeps
 * focus clear of it), except on short viewports, where it scrolls away (UI-ISS-014).
 */
export function MobileNav({ title, ask, ...sidebar }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <header
      className={cn(
        "sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-line bg-panel px-4 md:hidden",
        STATIC_WHEN_SHORT,
      )}
    >
      <span className="bg-shell-gradient size-8 shrink-0 rounded-lg" aria-hidden />
      <p className="min-w-0 flex-1 truncate text-base font-semibold">{title}</p>
      {ask}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          aria-label="Open menu"
          className="grid size-10 place-items-center rounded-lg text-fg-secondary hover:bg-hover hover:text-fg"
        >
          <Menu className="size-5" aria-hidden />
        </SheetTrigger>
        {/* The expanded sidebar's layout at its 232 px width; rows are 40 px for touch. The drawer
            is panel, like the sidebar, not the overlay surface (DESIGN_SYSTEM §1.1, D-12): the one
            sheet that sets its surface. Its edge is the sheet's own `line` border. */}
        <SheetContent
          side="left"
          showCloseButton={false}
          className="w-64 gap-0 bg-panel p-3 data-[side=left]:w-64 sm:max-w-64 data-[side=left]:sm:max-w-64"
        >
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <AppSidebar {...sidebar} collapsed={false} onNavigate={() => setOpen(false)} className="w-full" />
        </SheetContent>
      </Sheet>
    </header>
  );
}
