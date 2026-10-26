import { IndianRupee, Radio, ShoppingBag, Table2, Webhook } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Badge } from "@/components/ui/badge";
import { SECTION_IDS } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { Container, MARKETING_CARD, MARKETING_CARD_HOVER, SectionHeading } from "./primitives";

type Integration = {
  name: string;
  body: string;
  /** What is true today, in a few words (C-122, C-138). */
  status: string;
  tone: "success" | "neutral" | "brand";
  mark: ReactNode;
  tile: string;
};

const BRAND_TILE = "bg-brand-soft text-brand-fg";

// One line each, and the honest status: what runs today, what waits for Meta's approval, what
// arrives with our Shopify app listing, and what is yours (C-108, C-111, C-116, C-120, C-122).
// Logos only for the platforms we already ship as glyphs; everything else is an icon and a name.
export const INTEGRATIONS: Integration[] = [
  {
    name: "Instagram",
    body: "DMs, comments, publishing and insights for Business and Creator accounts, with Instagram's own login.",
    status: "Official API",
    tone: "success",
    mark: <PlatformGlyph platform="instagram" className="size-5 text-on-brand" />,
    tile: "bg-instagram-logo-gradient",
  },
  {
    name: "WhatsApp",
    body: "A WhatsApp Business number your business owns, through Meta's Embedded Signup. Meta bills its fees to you.",
    status: "Official API",
    tone: "success",
    mark: <PlatformGlyph platform="whatsapp" className="size-5 text-on-brand" />,
    tile: "bg-whatsapp-logo",
  },
  {
    name: "Website chat",
    body: "A chat widget for your own site that answers from your knowledge, in the same inbox.",
    status: "On every plan",
    tone: "success",
    mark: <PlatformGlyph platform="web" className="size-5 text-on-brand" />,
    tile: "bg-web",
  },
  {
    name: "Facebook Pages",
    body: "Messenger chats and Page comments in the same inbox, and publishing to your Page.",
    status: "With Meta's approval",
    tone: "neutral",
    mark: <PlatformGlyph platform="facebook" className="size-5 text-on-brand" />,
    tile: "bg-facebook-logo",
  },
  {
    name: "Live comments and ad replies",
    body: "Answer comments made during an Instagram Live, and chats that start from an ad.",
    status: "With Meta's approval",
    tone: "neutral",
    mark: <Radio className="size-5" aria-hidden />,
    tile: BRAND_TILE,
  },
  {
    name: "Shopify",
    body: "Bring your products in and keep prices and stock in step.",
    status: "With our Shopify app listing",
    tone: "neutral",
    mark: <ShoppingBag className="size-5" aria-hidden />,
    tile: BRAND_TILE,
  },
  {
    name: "Razorpay and UPI",
    body: "Payment links and UPI requests in the chat. The money goes to your own account, never through us.",
    status: "Your own account",
    tone: "brand",
    mark: <IndianRupee className="size-5" aria-hidden />,
    tile: BRAND_TILE,
  },
  {
    name: "Google Sheets",
    body: "Send leads to a spreadsheet you own, as they arrive.",
    status: "Pro and Max",
    tone: "brand",
    mark: <Table2 className="size-5" aria-hidden />,
    tile: BRAND_TILE,
  },
  {
    name: "Zapier and the public API",
    body: "Connect to other tools with Zapier, webhooks and API keys.",
    status: "Pro and Max",
    tone: "brand",
    mark: <Webhook className="size-5" aria-hidden />,
    tile: BRAND_TILE,
  },
];

/** What Amplychat connects to, each with one line and an honest status. Replaces the old platforms strip (C-138). */
export function Integrations() {
  return (
    <section id={SECTION_IDS.integrations} aria-labelledby="integrations-title" className="scroll-mt-24 border-t border-line-subtle py-16 sm:py-20">
      <Container>
        <SectionHeading
          id="integrations-title"
          eyebrow="Integrations"
          title="Connects to where your customers are"
          intro="Instagram and WhatsApp connect only through Meta's official APIs, and we never ask for your password. Each card says what runs today."
        />
        <ul className="mx-auto mt-12 grid max-w-6xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {INTEGRATIONS.map((item, index) => (
            <li key={item.name} data-reveal style={{ "--reveal-delay": `${(index % 3) * 80}ms` } as CSSProperties}>
              <div className={cn(MARKETING_CARD, MARKETING_CARD_HOVER, "flex h-full gap-4 p-4")}>
                <span className={cn("grid size-11 shrink-0 place-items-center rounded-xl", item.tile)}>{item.mark}</span>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold">{item.name}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-fg-secondary">{item.body}</p>
                  <Badge size="md" tone={item.tone} className="mt-2.5">
                    {item.status}
                  </Badge>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
