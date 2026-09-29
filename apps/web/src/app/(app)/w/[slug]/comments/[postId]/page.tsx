"use client";

import { useParams } from "next/navigation";

import { PostDetailPage } from "@/components/comments/PostDetailPage";

/** UX-SCR-05 post detail. Keyed by id, so no filter, composer or age survives a switch of post. */
export default function PostRoute() {
  const { postId } = useParams<{ postId: string }>();
  return <PostDetailPage key={postId} postId={postId} />;
}
