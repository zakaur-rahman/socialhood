import type { Metadata } from "next";

import { UploadTicketPage } from "@/components/upload/UploadTicketPage";

export const metadata: Metadata = { title: "Upload a file" };

/** C-165: the page an AI app links to, where a member drops the file it asked for. */
export default async function UploadTicketRoute({ params }: { params: Promise<{ ticket: string }> }) {
  const { ticket } = await params;
  return <UploadTicketPage ticketId={ticket} />;
}
