import type { Metadata } from "next";

import { EntryLinksPage } from "@/components/automations/EntryLinksPage";

export const metadata: Metadata = { title: "Entry links" };

/** GR-08: ig.me links and QR codes that open a chat and start an automation. */
export default function EntryLinksRoute() {
  return <EntryLinksPage />;
}
