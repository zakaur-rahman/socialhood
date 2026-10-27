import type { Metadata } from "next";

import { WidgetSettingsPage } from "@/components/widget/WidgetSettingsPage";

export const metadata: Metadata = { title: "Website chat" };

/** GR-28: the website chat widget's sites, look, visitor form and branding. */
export default function WidgetRoute() {
  return <WidgetSettingsPage />;
}
