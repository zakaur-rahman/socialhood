import type { Metadata } from "next";

import { MembersPage } from "@/components/team/MembersPage";

export const metadata: Metadata = { title: "Members" };

/** GR-19: who works in the workspace and as what; owners and admins. */
export default function MembersRoute() {
  return <MembersPage />;
}
