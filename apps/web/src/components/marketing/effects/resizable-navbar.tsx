"use client";

import { useEffect, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Resizable Navbar, from Aceternity UI's free "resizable-navbar"
 * (ui.aceternity.com/components/resizable-navbar), adapted for Social Hood (C-068):
 * - one bar for every width (the original rendered a desktop and a phone copy); the links and
 *   account actions are the caller's, so the header keeps its landmarks and phone menu;
 * - past `threshold` px of scroll the bar floats: it narrows (on wide screens), drops 12 px,
 *   rounds and gets the panel surface. CSS transitions on named properties do it, so no animation
 *   library code runs per frame, the page never reflows (the header keeps its height) and
 *   reduced motion makes the change instant;
 * - a passive scroll listener instead of motion's useScroll: the header is on every public page,
 *   and the legal pages then load no animation library at all;
 * - the panel, line and floating-shadow tokens instead of white/neutral, and the motion tokens
 *   (`duration-slow`, `ease-standard`); the blur is the marketing header's documented exception
 *   (DESIGN_SYSTEM §6), over a mostly opaque panel.
 */
export function Navbar({ children, className, threshold = 64 }: { children: ReactNode; className?: string; threshold?: number }) {
  const [floating, setFloating] = useState(false);
  useEffect(() => {
    const update = () => setFloating(window.scrollY > threshold);
    update(); // a page opened part-way down (a #section link, a reload)
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, [threshold]);
  return (
    <header data-floating={floating || undefined} className={cn("group/nav sticky top-0 z-40 px-3 sm:px-4", className)}>
      {children}
    </header>
  );
}

export function NavBody({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "relative mx-auto flex h-16 w-full max-w-6xl items-center gap-4 rounded-none border border-transparent px-3 sm:px-4",
        "transition-[max-width,translate,border-radius,background-color,border-color,box-shadow] duration-slow ease-standard motion-reduce:transition-none",
        "group-data-[floating]/nav:translate-y-3 group-data-[floating]/nav:rounded-2xl group-data-[floating]/nav:border-line",
        "group-data-[floating]/nav:bg-panel/85 group-data-[floating]/nav:shadow-floating group-data-[floating]/nav:backdrop-blur-md",
        "lg:group-data-[floating]/nav:max-w-4xl",
        className,
      )}
    >
      {children}
    </div>
  );
}
