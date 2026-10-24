import type { Metadata } from "next";

import { BroadcastsPage } from "@/components/broadcasts/BroadcastsPage";

export const metadata: Metadata = { title: "Broadcasts" };

/** GR-23: WhatsApp broadcasts, behind the BROADCASTS_ENABLED server setting. */
export default function BroadcastsRoute() {
  return <BroadcastsPage />;
}
