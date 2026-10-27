"use client";

import { useParams } from "next/navigation";

import { BroadcastDetailPage } from "@/components/broadcasts/BroadcastDetailPage";
import { useBroadcast } from "@/lib/api/queries";
import { useDocumentTitle } from "@/lib/document-title";
import { useCurrentWorkspace } from "@/lib/workspace";

/** GR-23: one broadcast. Keyed by id, so the people list and filter don't carry over. */
export default function BroadcastRoute() {
  const { id } = useParams<{ id: string }>();
  return (
    <>
      <BroadcastTitle id={id} />
      <BroadcastDetailPage key={id} id={id} />
    </>
  );
}

/** The tab's title is the broadcast's name. */
function BroadcastTitle({ id }: { id: string }) {
  const workspace = useCurrentWorkspace();
  const broadcast = useBroadcast(workspace.id, id);
  useDocumentTitle(broadcast.data?.name ?? "Broadcast");
  return null;
}
