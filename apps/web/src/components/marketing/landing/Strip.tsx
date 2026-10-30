import table from "@/lib/marketing/plan-table.json";

const number = new Intl.NumberFormat("en-US");

/** The Free plan's allowances come from plan-table.json (the API's plan table), never typed here. */
export const FREE = {
  aiCredits: table.entitlements.ai_credits_monthly.free,
  automations: table.entitlements.active_automations.free,
  // billing/plans.py widget_conversations_daily; services/widget/chat.py counts each new chat against it.
  websiteChats: table.entitlements.widget_conversations_daily.free,
};

/**
 * A few plain facts under the hero (C-138's numbers, in C-155's strip; C-157 sets them as the hero's
 * bottom edge; Hero renders it as the section's last part, C-157 hero spacing). Only things that are true by construction: what is built, and what the Free plan
 * includes. No customer counts, no speed or setup-time claims we can't back.
 */
export const STRIP: { value: string; label: string }[] = [
  { value: "1 inbox", label: "For Instagram, WhatsApp and your website chat." },
  { value: `${number.format(FREE.aiCredits)} AI credits`, label: "Every month on the Free plan." },
  { value: `${number.format(FREE.automations)} automations`, label: "Comment and DM automations on the Free plan." },
  { value: `${number.format(FREE.websiteChats)} website chats`, label: "New chats a day on your site, on the Free plan." },
];

export function Strip() {
  return (
    <section className="strip" aria-label="The product in numbers">
      <ul className="wrap strip-in">
        {STRIP.map((item) => (
          <li key={item.value}>
            <b className="num">{item.value}</b>
            {item.label}
          </li>
        ))}
      </ul>
    </section>
  );
}
