import { GtmPageView } from "@/components/marketing/GtmPageView";
import { COMPARE_MANYCHAT } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({ title: COMPARE_MANYCHAT.title, description: COMPARE_MANYCHAT.description, path: COMPARE_MANYCHAT.path });

/** GR-37: a go-to-market page, rendered from lib/marketing/gtm-pages.ts. Static. */
export default function Page() {
  return <GtmPageView page={COMPARE_MANYCHAT} />;
}
