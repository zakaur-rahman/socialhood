import type { Metadata } from "next";

import { BroadcastComposer } from "@/components/broadcasts/BroadcastComposer";

export const metadata: Metadata = { title: "New broadcast" };

export default function NewBroadcastRoute() {
  return <BroadcastComposer />;
}
