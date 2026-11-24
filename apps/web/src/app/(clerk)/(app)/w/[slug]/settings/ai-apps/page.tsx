import type { Metadata } from "next";

import { AiConnectionsPage } from "@/components/ai-connections/AiConnectionsPage";

export const metadata: Metadata = { title: "MCP & API" };

/** C-165 Settings › MCP & API: the AI connections mode and every connected app. */
export default function AiAppsRoute() {
  return <AiConnectionsPage />;
}
