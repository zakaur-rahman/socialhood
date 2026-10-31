import { AutomationPageView, automationMetadata } from "@/components/marketing/automations/AutomationPageView";
import { automationPage } from "@/lib/marketing/automation-pages";

/** /whatsapp/auto-reply (C-163): one of the automation and channel pages, from lib/marketing/automation-pages. Static. */
const PAGE = automationPage("/whatsapp/auto-reply");

export const metadata = automationMetadata(PAGE);

export default function Page() {
  return <AutomationPageView page={PAGE} />;
}
