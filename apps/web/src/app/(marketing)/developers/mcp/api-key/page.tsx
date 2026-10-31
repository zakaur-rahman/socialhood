import { McpApiKeyView } from "@/components/marketing/developers/McpApiKeyView";
import { API_KEY_META, API_KEY_PAGE_PATH } from "@/lib/marketing/mcp-api-key";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ ...API_KEY_META, path: API_KEY_PAGE_PATH });

/** C-165: connecting an AI app with an Amplychat API key. Static. */
export default function McpApiKeyPage() {
  return <McpApiKeyView apiBase={process.env.NEXT_PUBLIC_API_BASE_URL} />;
}
