"use client";

import type { ReactNode } from "react";

import { InboxShell } from "@/components/inbox/InboxShell";

/** UX-INB-01: the list and details panes stay mounted while the thread (the page) changes. */
export default function InboxLayout({ children }: { children: ReactNode }) {
  return <InboxShell>{children}</InboxShell>;
}
