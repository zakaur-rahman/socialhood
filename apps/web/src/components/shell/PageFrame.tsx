import { cn } from "@/lib/utils";
import { PAGE_TITLE } from "@/styles/tokens";
import { ChevronLeft } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * UX-SH-03: title and optional actions in a header row, content below, max width 1200 px. A page
 * below another (a post under Comments) shows a back link above the title. The header row wraps
 * (UI-ISS-056): at 320 px the actions move under the title instead of pushing the page sideways.
 */
/**
 * A page's header row stays in view while the page scrolls (owner, 2026-10-24): sticky under the
 * phone's top bar (h-14) and at the top from md, on the work-pane glass so what scrolls beneath it
 * blurs. It bleeds over the page's padding (p-4 / md:p-6) so the glass reaches both edges. Pages
 * that build their own header (Home, Schedule, the post composer) use it too.
 */
export const STICKY_PAGE_HEADER =
  "glass-pane sticky top-14 z-20 -mx-4 border-b border-line px-4 py-3 md:top-0 md:-mx-6 md:px-6";

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
  return (
    <div className="w-full p-4 pt-0 md:p-6 md:pt-0">
      <div className={cn(STICKY_PAGE_HEADER, "mb-6 pt-4 md:pt-6")}>
        {back ? <BackLink {...back} /> : null}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <h1 className={cn("min-w-0 break-words", PAGE_TITLE)}>{title}</h1>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      </div>
      {children}
    </div>
  );
}
