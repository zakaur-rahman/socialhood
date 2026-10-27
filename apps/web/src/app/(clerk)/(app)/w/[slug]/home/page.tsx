import type { Metadata } from "next";

import { HomeScreen } from "@/components/home/HomeScreen";

export const metadata: Metadata = { title: "Home" };

/** /w/[slug]/home: the checklist and the overview (UX-SCR-01). */
export default function HomePage() {
  return <HomeScreen />;
}
