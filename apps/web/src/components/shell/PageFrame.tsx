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
    <div className="w-full p-4 md:p-6">
      {back ? <BackLink {...back} /> : null}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <h1 className={cn("min-w-0 break-words", PAGE_TITLE)}>{title}</h1>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </div>
  );
}
