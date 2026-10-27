import type { Metadata } from "next";

import { MentionsPage } from "@/components/comments/MentionsPage";

export const metadata: Metadata = { title: "Story mentions" };

/** GR-07: who mentioned the account in their story. */
export default function MentionsRoute() {
  return <MentionsPage />;
}
