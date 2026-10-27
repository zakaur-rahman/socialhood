import type { Metadata } from "next";

import { EmptyState } from "@/components/states/EmptyState";
import { emptyStates } from "@/lib/copy";

export const metadata: Metadata = { title: "Inbox" };

/** Nothing selected: the thread pane explains what to do (on phones the list shows instead). */
export default function InboxPage() {
  return <EmptyState className="h-full" {...emptyStates.inboxNothingSelected} />;
}
