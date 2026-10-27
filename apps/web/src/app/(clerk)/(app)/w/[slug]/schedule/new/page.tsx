import type { Metadata } from "next";

import { NewPostRoute } from "@/components/composer/routes";

export const metadata: Metadata = { title: "New post" };

/** F-13 New post: creates a draft and opens the composer on it. */
export default function NewScheduledPostPage() {
  return <NewPostRoute />;
}
