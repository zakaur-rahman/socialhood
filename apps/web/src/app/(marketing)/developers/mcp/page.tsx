import { ConnectAiView } from "@/components/marketing/developers/ConnectAiView";
import { CONNECT_AI_META, CONNECT_AI_PATH } from "@/lib/marketing/connect-ai";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ ...CONNECT_AI_META, path: CONNECT_AI_PATH });

/** C-165 phase C: the public setup guide for the MCP server (Claude, ChatGPT, Codex). Static. */
export default function ConnectAiPage() {
  return <ConnectAiView apiBase={process.env.NEXT_PUBLIC_API_BASE_URL} />;
}
