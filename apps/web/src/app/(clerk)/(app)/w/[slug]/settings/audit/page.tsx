import type { Metadata } from "next";

import { AuditLogPage } from "@/components/team/AuditLogPage";

export const metadata: Metadata = { title: "Audit log" };

/** GR-19: who sent, edited or deleted what; owners and admins. */
export default function AuditRoute() {
  return <AuditLogPage />;
}
