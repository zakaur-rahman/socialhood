import type { Metadata } from "next";

import { KnowledgePage } from "@/components/knowledge/KnowledgePage";

export const metadata: Metadata = { title: "Knowledge" };

/** UX-SCR-06. */
export default function KnowledgeRoute() {
  return <KnowledgePage />;
}
