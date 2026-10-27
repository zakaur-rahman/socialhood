"use client";

import { useParams } from "next/navigation";

import { PostDetailPage } from "@/components/comments/PostDetailPage";
import { usePost } from "@/lib/api/queries";
import { mediaTypeLabel } from "@/lib/comments/format";
import { useDocumentTitle } from "@/lib/document-title";
import { formatDay } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

/** UX-SCR-05 post detail. Keyed by id, so no filter, composer or age survives a switch of post. */
export default function PostRoute() {
  const { postId } = useParams<{ postId: string }>();
  return (
    <>
      <PostTitle postId={postId} />
      <PostDetailPage key={postId} postId={postId} />
    </>
  );
}

/** The tab's title names the post, like the page's heading does (UI-ISS-061). */
function PostTitle({ postId }: { postId: string }) {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const post = usePost(workspace.id, postId);
  useDocumentTitle(
    post.data
      ? `Comments · ${mediaTypeLabel(post.data.media_type)} from ${formatDay(post.data.posted_at, workspace.timezone, now)}`
      : "Comments",
  );
  return null;
}
