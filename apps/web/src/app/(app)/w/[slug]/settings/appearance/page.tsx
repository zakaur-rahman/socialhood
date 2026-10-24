import type { Metadata } from "next";

import { AppearancePage } from "@/components/settings/AppearancePage";

export const metadata: Metadata = { title: "Appearance" };

/** C-102 Appearance: the member's own theme, Dark, Light or System. */
export default function AppearanceRoute() {
  return <AppearancePage />;
}
