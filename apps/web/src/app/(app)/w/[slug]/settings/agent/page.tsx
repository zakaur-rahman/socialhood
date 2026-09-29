import type { Metadata } from "next";

import { AgentSettingsPage } from "@/components/agent/AgentSettingsPage";

export const metadata: Metadata = { title: "Ask Social Hood settings" };

/** FR-AGT-07: the agent's mode and every run, for owners and admins (agent-architecture.html §12). */
export default function AgentSettingsRoute() {
  return <AgentSettingsPage />;
}
