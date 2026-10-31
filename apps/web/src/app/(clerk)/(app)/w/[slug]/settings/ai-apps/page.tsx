import type { Metadata } from "next";

import { AiConnectionsPage } from "@/components/ai-connections/AiConnectionsPage";

export const metadata: Metadata = { title: "Connected AI apps" };

/** C-165 Settings › Connected AI apps: the AI connections mode and every connected app. */
export default function AiAppsRoute() {
  return <AiConnectionsPage />;
}
