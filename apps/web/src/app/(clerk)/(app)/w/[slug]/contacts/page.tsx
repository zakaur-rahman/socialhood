import type { Metadata } from "next";

import { ContactsPage } from "@/components/contacts/ContactsPage";

export const metadata: Metadata = { title: "Contacts" };

/** GR-17: the contacts list with filters, segments, bulk tagging and export. */
export default function ContactsRoute() {
  return <ContactsPage />;
}
