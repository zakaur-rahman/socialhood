import type { Metadata } from "next";

import { StartersPage } from "@/components/automations/StartersPage";

export const metadata: Metadata = { title: "Conversation starters" };

/** GR-11: an Instagram account's conversation starters (ice breakers). */
export default function StartersRoute() {
  return <StartersPage />;
}
