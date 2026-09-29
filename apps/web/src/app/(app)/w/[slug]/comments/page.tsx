import type { Metadata } from "next";

import { CommentsPage } from "@/components/comments/CommentsPage";

export const metadata: Metadata = { title: "Comments" };

/** UX-SCR-05: the posts grid. */
export default function CommentsRoute() {
  return <CommentsPage />;
}
