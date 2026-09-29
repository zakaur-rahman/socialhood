"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/states/PageSkeleton";

import { AdminOnly, NewPost } from "./NewPost";
import { PostComposer } from "./PostComposer";

function ComposerWithParams() {
  const { id } = useParams<{ id: string }>();
  const when = useSearchParams().get("when") === "queue" ? "queue" : "time";
  return <PostComposer key={id} id={id} initialWhen={when} />;
}

/**
 * /w/{slug}/schedule/{id}[?when=queue] (UX-SCR-13). Keyed by id, so no draft state survives a
 * switch of post; ?when=queue opens a draft on Add to queue.
 */
export function ComposerRoute() {
  return (
    <AdminOnly>
      <Suspense fallback={<PageSkeleton />}>
        <ComposerWithParams />
      </Suspense>
    </AdminOnly>
  );
}

function NewPostWithParams() {
  const params = useSearchParams();
  return <NewPost at={params.get("at")} when={params.get("when")} />;
}

/**
 * /w/{slug}/schedule/new[?at=ISO instant][&when=queue]: New post, or a click on an empty calendar
 * time (F-13).
 */
export function NewPostRoute() {
  return (
    <AdminOnly>
      <Suspense fallback={<PageSkeleton rows={3} />}>
        <NewPostWithParams />
      </Suspense>
    </AdminOnly>
  );
}
