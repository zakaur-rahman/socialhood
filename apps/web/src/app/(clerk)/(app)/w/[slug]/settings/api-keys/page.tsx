import type { Metadata } from "next";

import { ApiKeysPage } from "@/components/integrations/ApiKeysPage";

export const metadata: Metadata = { title: "API keys" };

/** C-165 Settings › API keys: keys for the public API and for AI apps over MCP, on their own page. */
export default function ApiKeysRoute() {
  return <ApiKeysPage />;
}
