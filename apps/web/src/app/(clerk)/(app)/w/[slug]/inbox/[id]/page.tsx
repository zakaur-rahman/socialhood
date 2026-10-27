"use client";

import { useParams } from "next/navigation";

import { ThreadView } from "@/components/inbox/ThreadView";

/** TR-FE-06: keyed by conversation id, so no state survives a switch. */
export default function ConversationPage() {
  const { id } = useParams<{ id: string }>();
  return <ThreadView key={id} conversationId={id} />;
}
