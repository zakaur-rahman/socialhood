import { GtmPageView } from "@/components/marketing/GtmPageView";
import { COMPARE_INTERAKT } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: COMPARE_INTERAKT.title, description: COMPARE_INTERAKT.description, path: COMPARE_INTERAKT.path });

/** GR-37: a go-to-market page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={COMPARE_INTERAKT} />;
}
