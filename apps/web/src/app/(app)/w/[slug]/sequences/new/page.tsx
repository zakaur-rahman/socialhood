import type { Metadata } from "next";

import { SequenceForm } from "@/components/sequences/SequenceForm";

export const metadata: Metadata = { title: "New sequence" };

export default function NewSequenceRoute() {
  return <SequenceForm />;
}
