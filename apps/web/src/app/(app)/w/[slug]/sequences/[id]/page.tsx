"use client";

import { useParams } from "next/navigation";

import { SequenceDetailPage } from "@/components/sequences/SequenceDetailPage";
import { useSequence } from "@/lib/api/queries";
import { useDocumentTitle } from "@/lib/document-title";
import { useCurrentWorkspace } from "@/lib/workspace";

/** GR-24: one sequence. Keyed by id, so the people list and its filter don't carry over. */
export default function SequenceRoute() {
  const { id } = useParams<{ id: string }>();
  return (
    <>
      <SequenceTitle id={id} />
      <SequenceDetailPage key={id} id={id} />
    </>
  );
}

/** The tab's title is the sequence's name. */
function SequenceTitle({ id }: { id: string }) {
  const workspace = useCurrentWorkspace();
  const sequence = useSequence(workspace.id, id);
  useDocumentTitle(sequence.data?.name ?? "Sequence");
  return null;
}
