import type { Metadata } from "next";

import { AiSettingsPage } from "@/components/ai/AiSettingsPage";

export const metadata: Metadata = { title: "AI settings" };

/** UX-SCR-07 AI (T5.5). */
export default function AiSettingsRoute() {
  return <AiSettingsPage />;
}
