import { GtmPageView } from "@/components/marketing/GtmPageView";
import { SWITCH_PAGE } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: SWITCH_PAGE.title, description: SWITCH_PAGE.description, path: SWITCH_PAGE.path });

/** GR-37: a go-to-market page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={SWITCH_PAGE} />;
}
