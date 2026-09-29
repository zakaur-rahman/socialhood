import type { Metadata } from "next";

import { AskPage } from "@/components/agent/AskPage";

export const metadata: Metadata = { title: "Ask Social Hood" };

/** FR-AGT-01: Ask Social Hood as a full page with thread history (agent-architecture.html §12). */
export default function AskRoute() {
  return <AskPage />;
}
