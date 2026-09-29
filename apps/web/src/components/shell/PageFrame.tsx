import { ChevronLeft } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * UX-SH-03: title and optional actions in a header row, content below, max width 1200 px. A page
 * below another (a post under Comments) shows a back link above the title.
 */
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
    <div className="mx-auto w-full max-w-[1200px] p-4 md:p-6">
      {back ? (
        <Link
          href={back.href}
          className="-ml-1 mb-1 inline-flex min-h-10 items-center gap-1 rounded-md px-1 text-sm text-fg-secondary hover:text-fg md:min-h-8"
        >
          <ChevronLeft className="size-4" aria-hidden /> {back.label}
        </Link>
      ) : null}
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </div>
  );
}
