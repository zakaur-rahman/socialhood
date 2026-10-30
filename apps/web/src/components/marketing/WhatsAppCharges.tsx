import { ArrowUpRight, BadgeCheck, Clock, Receipt } from "lucide-react";

import { SITE_NAME } from "@/lib/marketing/site";

import { Ico } from "./landing/Ico";

/** Meta's own WhatsApp pricing page, linked rather than copied: its rates change by country and date. */
export const META_WHATSAPP_PRICING_URL = "https://developers.facebook.com/docs/whatsapp/pricing";

/**
 * WhatsApp message charges on the pricing page (C-156). Owner decision 2026-10-29: customers pay
 * Meta directly through their own WhatsApp Business account, and Amplychat adds no markup. Meta's
 * model as its pricing page describes it (per template message, by category and the recipient's
 * country code; free-form replies inside the customer service window aren't charged); no rates are
 * written here, they change.
 *
 * C-159 look: one card, the two rules side by side with their icons, then who pays as a callout
 * row, and Meta's page as the card's foot.
 */
export function WhatsAppCharges() {
  return (
    <section id="whatsapp-charges" aria-labelledby="whatsapp-charges-title" className="band pp scroll-mt-24">
      <div className="wrap">
        <div className="wa-card">
          <h2 id="whatsapp-charges-title" className="h-sec">
            WhatsApp message charges
          </h2>
          <div className="wa-grid">
            <div className="wa-rule">
              <Ico icon={Receipt} />
              <p>
                Meta charges for WhatsApp template messages, the pre-approved messages a business sends to start or restart a
                conversation. The charge depends on the template&apos;s category (marketing, utility or authentication) and the
                country of the person you send it to.
              </p>
            </div>
            <div className="wa-rule">
              <Ico icon={Clock} />
              <p>
                When a customer messages you, a 24-hour window opens. Inside it you can reply freely, and Meta doesn&apos;t charge
                for those replies. After 24 hours without a message from them, you can only reach them with a template.
              </p>
            </div>
          </div>
          <div className="pp-callout wa-pay">
            <Ico icon={BadgeCheck} />
            <div>
              <p className="wa-strong">You pay Meta directly through your own WhatsApp Business account. {SITE_NAME} adds no markup.</p>
              <p>These charges are separate from your {SITE_NAME} plan, and Instagram messages have no such charge.</p>
            </div>
          </div>
          <p className="wa-foot">
            <a href={META_WHATSAPP_PRICING_URL} rel="noopener noreferrer" className="tlink">
              Meta&apos;s WhatsApp pricing and current rates
            </a>
            <ArrowUpRight className="size-4" aria-hidden />
          </p>
        </div>
      </div>
    </section>
  );
}
