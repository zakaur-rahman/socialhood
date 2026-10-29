import { GtmPageView } from "@/components/marketing/GtmPageView";
import { COMPARE_SPUR } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: COMPARE_SPUR.title, description: COMPARE_SPUR.description, path: COMPARE_SPUR.path });

/** C-156: a comparison page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={COMPARE_SPUR} />;
}
