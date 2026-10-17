"use client";

import { PAGE_TITLE } from "@/styles/tokens";
import type { ReactNode } from "react";

/**
 * Every settings tab's header (C-066, amended by D-08): the title, one line of description and the
 * page's actions on the right. No breadcrumb and no eyebrow: the tab bar above already names the
 * page, and its label equals this title. The title is 24 px like every page title (D-05).
 */
export function SettingsPageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0 space-y-1.5">
        <h1 className={PAGE_TITLE}>{title}</h1>
        <p className="max-w-2xl text-sm text-fg-secondary">{description}</p>
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/** A settings page: the header, then the page's cards, then (for a form) its save bar. */
export function SettingsFrame({ header, children }: { header: ReactNode; children: ReactNode }) {
  return (
    <div className="w-full space-y-6 px-4 pt-5 pb-6 md:px-6 md:pt-6">
      {header}
      {children}
    </div>
  );
}
