"use client";

import { cn } from "@/lib/utils";
import { PAGE_TITLE } from "@/styles/tokens";
import { ChevronLeft } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { type ReactNode, useEffect, useRef } from "react";

/**
 * UX-SH-03: title and optional actions in a header row, content below, max width 1200 px. A page
 * below another (a post under Comments) shows a back link above the title. The header row wraps
 * (UI-ISS-056): at 320 px the actions move under the title instead of pushing the page sideways.
 */
/**
 * A page's header row stays in view while the page scrolls (owner, 2026-10-24): sticky under the
 * phone's top bar (h-14), a band over the page's padding (-mx-4). From md it is a card like the
 * ones below it (owner, 2026-11-06): their width, rounded, a thin edge, 16 px under the top (or the
 * banners), with a strip of canvas above it (`before:`) so rows scrolling past don't show in that
 * gap. Pages that build their own header (Home, Schedule, the post composer) use it too.
 */
export const STICKY_PAGE_HEADER =
  "bg-panel sticky top-14 z-20 -mx-4 border-b border-line px-4 py-3 md:top-[calc(var(--banner-h,0px)+1rem)] md:mx-0 md:mt-4 md:rounded-xl md:border md:border-line-card md:px-5 md:py-4 md:shadow-surface md:before:pointer-events-none md:before:absolute md:before:-inset-x-px md:before:-top-[calc(1rem+1px)] md:before:h-4 md:before:bg-canvas md:before:content-['']";

/**
 * A list's search and filter row, which stays in view just under the sticky page header while the
 * list scrolls (owner, 2026-11-06). On the page's canvas, bleeding over its padding like the header;
 * z-20 like the header, above the rows' own z-10 parts (avatar badges, row controls). The padding
 * keeps rows off it while stuck; -mt-2 takes it back on top, so the gap under the header stays 24 px.
 */
export const STICKY_PAGE_TOOLBAR =
  "bg-canvas sticky top-[calc(3.5rem+var(--page-header-h,0px))] z-20 -mx-4 -mt-2 px-4 py-2 md:top-[calc(var(--banner-h,0px)+var(--page-header-h,0px))] md:-mx-6 md:px-6";

/**
 * The header's height with its top gap, as --page-header-h on the page, so a sticky bar inside the
 * page (a list's toolbar, the comment filters, a side panel) sits just under the sticky header. Only
 * the variable on the page's element is written (no React state, no re-render).
 */
export function usePageHeaderHeight<H extends HTMLElement>() {
  const header = useRef<H>(null);
  const page = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = header.current;
    const root = page.current;
    if (!element || !root || typeof ResizeObserver === "undefined") return;
    const sync = () =>
      root.style.setProperty(
        "--page-header-h",
        `${element.offsetHeight + (Number.parseFloat(getComputedStyle(element).marginTop) || 0)}px`,
      );
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { header, page };
}

/** The "‹ Parent" link above a child page's title (D-16). Replaces the old Breadcrumb landmark. */
export function BackLink({ href, label }: { href: Route; label: string }) {
  return (
    <Link
      href={href}
      className="-ml-1 mb-1 inline-flex min-h-8 items-center gap-1 rounded-md px-1 text-sm text-fg-secondary hover:text-fg pointer-coarse:min-h-10"
    >
      <ChevronLeft className="size-4" aria-hidden /> {label}
    </Link>
  );
}

/** First-paint header height for a title-only header; the observer then writes the measured value. */
const PAGE_CLASS = "w-full p-4 pt-0 [--page-header-h:3.8125rem] md:p-6 md:pt-0 md:[--page-header-h:5.125rem]";

export function PageFrame({
  title,
  actions,
  back,
  children,
}: {
  title: string;
  actions?: ReactNode;
  back?: { href: Route; label: string };
  children: ReactNode;
}) {
  // PAGE_CLASS gives --page-header-h a first-paint value for a title-only header, so the first
  // paint and the measured value agree for the common case and nothing jumps after mount.
  const { header, page } = usePageHeaderHeight<HTMLDivElement>();
  return (
    <div ref={page} className={PAGE_CLASS}>
      <div ref={header} className={cn(STICKY_PAGE_HEADER, "mb-6 pt-4")}>
        {back ? <BackLink {...back} /> : null}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          {/* On a phone the top bar already names the page: the heading stays for screen readers. */}
          <h1 className={cn("min-w-0 break-words max-md:sr-only", PAGE_TITLE)}>{title}</h1>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      </div>
      {children}
    </div>
  );
}
