import type { Metadata, Route } from "next";

import { BackLink } from "@/components/shell/PageFrame";
import { WidgetSettingsPage } from "@/components/widget/WidgetSettingsPage";

export const metadata: Metadata = { title: "Website chat" };

/** GR-28, C-183: the website chat's sites, look, visitor form and branding, opened from Connections. */
export default async function WebsiteChatRoute({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <>
      <div className="px-4 pt-3 md:px-6">
        <BackLink href={`/w/${slug}/connections` as Route} label="Connections" />
      </div>
      <WidgetSettingsPage />
    </>
  );
}
