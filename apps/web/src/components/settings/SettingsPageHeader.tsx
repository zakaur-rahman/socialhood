"use client";

import { ChevronRight } from "lucide-react";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

import { currentSection } from "./sections";

/**
 * Every settings tab's header (C-066): a breadcrumb naming the tab the page is on (from the
 * address, so it can't name the wrong one), a small label, the title, one line of description and
 * the page's actions on the right. `card` puts it in a panel (Agent).
 */
export function SettingsPageHeader({
  label,
  title,
  description,
  actions,
  variant = "plain",
}: {
  label: string;
  title: string;
  description: ReactNode;
  actions?: ReactNode;
  variant?: "plain" | "card";
}) {
  const pathname = usePathname();
  const section = currentSection(pathname ?? "");
  return (
    <header className="space-y-4">
      <nav aria-label="Breadcrumb">
        <ol className="flex items-center gap-1.5 text-sm text-fg-secondary">
          <li>Settings</li>
          <li aria-hidden>
            <ChevronRight className="size-3.5" />
          </li>
          <li>
            <span aria-current="page" className="font-medium text-fg">
              {section?.label ?? title}
            </span>
          </li>
        </ol>
      </nav>
      <div
        className={cn(
          "flex flex-col gap-4 md:flex-row md:items-end md:justify-between",
          variant === "card" && "rounded-2xl border border-line bg-panel p-5 md:p-6",
        )}
      >
        <div className="min-w-0 space-y-1.5">
          <p className={cn(EYEBROW, "text-brand-fg")}>{label}</p>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
          <p className="max-w-2xl text-sm text-fg-secondary">{description}</p>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}

/** A settings page: the header, then the page's cards, then (for a form) its save bar. */
export function SettingsFrame({ header, children }: { header: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1200px] space-y-6 px-4 pt-5 pb-6 md:px-6 md:pt-6">
      {header}
      {children}
    </div>
  );
}
