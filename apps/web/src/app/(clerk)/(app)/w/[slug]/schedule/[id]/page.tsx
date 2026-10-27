import type { Metadata } from "next";

import { ComposerRoute } from "@/components/composer/routes";

export const metadata: Metadata = { title: "Post" };

/** UX-SCR-13: the post composer (F-13). */
export default function ScheduledPostPage() {
  return <ComposerRoute />;
}
