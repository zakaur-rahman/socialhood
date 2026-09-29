"use client";

import { Menu } from "lucide-react";
import { useState, type ComponentProps, type ReactNode } from "react";

import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

import { AppSidebar } from "./AppSidebar";

type Props = Omit<ComponentProps<typeof AppSidebar>, "collapsed" | "onNavigate" | "onToggleCollapsed" | "ask"> & {
  title: string;
  /** Ask Social Hood's button (FR-AGT-01), beside the menu. */
  ask?: ReactNode;
};

/**
 * UX-SH-02: below 768 px, a 56 px top bar with the logo, page title, Ask Social Hood and a menu
 * button. The drawer holds the expanded sidebar; it is closed on load and closes when a link is
 * tapped (v1 opened on load and stayed open).
 */
export function MobileNav({ title, ask, ...sidebar }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-line bg-panel px-4 md:hidden">
      <span className="bg-shell-gradient size-8 shrink-0 rounded-lg" aria-hidden />
      <p className="min-w-0 flex-1 truncate text-base font-semibold">{title}</p>
      {ask}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          aria-label="Open menu"
          className="grid size-10 place-items-center rounded-lg text-fg-secondary hover:bg-white/5 hover:text-fg"
        >
          <Menu className="size-5" aria-hidden />
        </SheetTrigger>
        {/* The expanded sidebar's layout at its 232 px width; rows are 40 px for touch. */}
        <SheetContent
          side="left"
          showCloseButton={false}
          className="w-[256px] gap-0 border-line bg-canvas p-3 data-[side=left]:w-[256px] sm:max-w-[256px] data-[side=left]:sm:max-w-[256px]"
        >
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <AppSidebar {...sidebar} collapsed={false} onNavigate={() => setOpen(false)} className="w-full" />
        </SheetContent>
      </Sheet>
    </header>
  );
}
