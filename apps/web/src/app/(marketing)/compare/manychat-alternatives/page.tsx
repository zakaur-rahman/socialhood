import { AlternativesView } from "@/components/marketing/AlternativesView";
import { ALTERNATIVES_PATH } from "@/lib/marketing/alternatives";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Manychat alternatives for Instagram and WhatsApp",
  description:
    "Nine Manychat alternatives side by side: what each suits, strengths, limits and starting prices from each vendor's own dated pages. Not a ranking.",
  path: ALTERNATIVES_PATH,
});

/** Manychat alternatives (C-163), from lib/marketing/alternatives.ts. Static. */
export default function ManychatAlternativesPage() {
  return <AlternativesView />;
}
