"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/states/PageSkeleton";

import { AdminOnly, NewPost } from "./NewPost";
import { PostComposer } from "./PostComposer";

/** /w/{slug}/schedule/{id} (UX-SCR-13). Keyed by id, so no draft state survives a switch of post. */
export function ComposerRoute() {
  const { id } = useParams<{ id: string }>();
  return (
    <AdminOnly>
      <PostComposer key={id} id={id} />
    </AdminOnly>
  );
}

function NewPostWithParams() {
  const params = useSearchParams();
  return <NewPost at={params.get("at")} />;
}

/** /w/{slug}/schedule/new[?at=ISO instant]: New post, or a click on an empty calendar time (F-13). */
export function NewPostRoute() {
  return (
    <AdminOnly>
      <Suspense fallback={<PageSkeleton rows={3} />}>
        <NewPostWithParams />
      </Suspense>
    </AdminOnly>
  );
}
