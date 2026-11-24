import type { Route } from "next";
import { redirect } from "next/navigation";

/** C-183: Website chat moved to Connections; old links and bookmarks land there. */
export default async function OldWidgetRoute({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  redirect(`/w/${slug}/connections/website` as Route);
}
