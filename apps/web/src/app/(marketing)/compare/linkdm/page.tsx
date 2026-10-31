import { GtmPageView } from "@/components/marketing/GtmPageView";
import { COMPARE_LINKDM } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: COMPARE_LINKDM.title, description: COMPARE_LINKDM.description, path: COMPARE_LINKDM.path });

/** C-156: a comparison page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={COMPARE_LINKDM} />;
}
