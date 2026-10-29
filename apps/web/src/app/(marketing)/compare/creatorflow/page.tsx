import { GtmPageView } from "@/components/marketing/GtmPageView";
import { COMPARE_CREATORFLOW } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: COMPARE_CREATORFLOW.title, description: COMPARE_CREATORFLOW.description, path: COMPARE_CREATORFLOW.path });

/** C-156: a comparison page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={COMPARE_CREATORFLOW} />;
}
