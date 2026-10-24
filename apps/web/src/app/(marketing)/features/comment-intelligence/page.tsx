import { GtmPageView } from "@/components/marketing/GtmPageView";
import { FEATURE_COMMENT_INTELLIGENCE } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: FEATURE_COMMENT_INTELLIGENCE.title, description: FEATURE_COMMENT_INTELLIGENCE.description, path: FEATURE_COMMENT_INTELLIGENCE.path });

/** GR-37: a go-to-market page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={FEATURE_COMMENT_INTELLIGENCE} />;
}
