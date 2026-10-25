import { GtmPageView } from "@/components/marketing/GtmPageView";
import { FEATURE_AI_INBOX } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: FEATURE_AI_INBOX.title, description: FEATURE_AI_INBOX.description, path: FEATURE_AI_INBOX.path });

/** GR-37: a go-to-market page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={FEATURE_AI_INBOX} />;
}
