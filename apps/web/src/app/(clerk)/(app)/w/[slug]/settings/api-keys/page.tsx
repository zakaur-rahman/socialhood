import type { Route } from "next";
import { redirect } from "next/navigation";

/** C-180: API keys are on Settings › MCP & API now; old links and bookmarks land on that section. */
export default async function ApiKeysRoute({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  redirect(`/w/${slug}/settings/ai-apps#api-keys` as Route);
}
