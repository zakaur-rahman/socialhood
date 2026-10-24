import { GtmPageView } from "@/components/marketing/GtmPageView";
import { FEATURE_PUBLISHING } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: FEATURE_PUBLISHING.title, description: FEATURE_PUBLISHING.description, path: FEATURE_PUBLISHING.path });

/** GR-37: a go-to-market page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={FEATURE_PUBLISHING} />;
}
