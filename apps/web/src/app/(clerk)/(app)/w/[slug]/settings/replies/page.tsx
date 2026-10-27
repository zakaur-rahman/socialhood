import type { Metadata } from "next";

import { SavedRepliesPage } from "@/components/replies/SavedRepliesPage";

export const metadata: Metadata = { title: "Saved replies" };

/** GR-21: the workspace's saved replies; owners and admins manage them, everyone reads. */
export default function SavedRepliesRoute() {
  return <SavedRepliesPage />;
}
