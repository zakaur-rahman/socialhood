import type { Metadata } from "next";

import { SequencesPage } from "@/components/sequences/SequencesPage";

export const metadata: Metadata = { title: "Sequences" };

/** GR-24: timed follow-up messages after something happens. */
export default function SequencesRoute() {
  return <SequencesPage />;
}
