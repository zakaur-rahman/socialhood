import { McpProductView } from "@/components/marketing/developers/McpProductView";
import { MCP_PAGE_META, MCP_PAGE_PATH } from "@/lib/marketing/mcp-page";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ ...MCP_PAGE_META, path: MCP_PAGE_PATH });

/** C-165: the MCP product page for business owners and creators. Static. */
export default function McpPage() {
  return <McpProductView />;
}
