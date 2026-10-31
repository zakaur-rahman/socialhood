import { AutomationPageView, automationMetadata } from "@/components/marketing/automations/AutomationPageView";
import { automationPage } from "@/lib/marketing/automation-pages";

/** /instagram/comment-to-dm (C-163): one of the automation and channel pages, from lib/marketing/automation-pages. Static. */
const PAGE = automationPage("/instagram/comment-to-dm");

export const metadata = automationMetadata(PAGE);

export default function Page() {
  return <AutomationPageView page={PAGE} />;
}
