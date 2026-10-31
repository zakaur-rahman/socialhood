import { GtmPageView } from "@/components/marketing/GtmPageView";
import { COMPARE_WATI } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: COMPARE_WATI.title, description: COMPARE_WATI.description, path: COMPARE_WATI.path });

/** C-156: a comparison page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={COMPARE_WATI} />;
}
