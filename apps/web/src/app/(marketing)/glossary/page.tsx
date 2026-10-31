import { GlossaryIndex } from "@/components/marketing/glossary/GlossaryView";
import { GLOSSARY_PATH } from "@/lib/marketing/glossary";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Meta messaging glossary: WhatsApp and Instagram",
  description:
    "WhatsApp, Instagram and Messenger terms in plain words: the 24-hour window, templates, opt-in, WABA, private replies and more, with Meta's sources.",
  path: GLOSSARY_PATH,
});

/** The glossary of Meta messaging terms (C-163), from lib/marketing/glossary. Static. */
export default function GlossaryPage() {
  return <GlossaryIndex />;
}
