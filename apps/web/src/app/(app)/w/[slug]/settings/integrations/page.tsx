import type { Metadata } from "next";

import { IntegrationsPage } from "@/components/integrations/IntegrationsPage";

export const metadata: Metadata = { title: "Integrations" };

/** GR-04 Settings › Integrations: outbound webhook endpoints and their delivery log. */
export default function IntegrationsRoute() {
  return <IntegrationsPage />;
}
