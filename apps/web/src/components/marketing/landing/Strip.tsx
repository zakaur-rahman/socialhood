import table from "@/lib/marketing/plan-table.json";

const number = new Intl.NumberFormat("en-US");

/** The Free plan's allowances come from plan-table.json (the API's plan table), never typed here. */
export const FREE = {
  aiCredits: table.entitlements.ai_credits_monthly.free,
  automations: table.entitlements.active_automations.free,
};

/**
 * A few plain facts under the hero (C-138's numbers, in C-155's strip). Only things that are true
 * by construction: what is built, and what the Free plan includes. No customer counts, no speed or
 * setup-time claims we can't back.
 */
export const STRIP: { value: string; label: string }[] = [
  { value: "1 inbox", label: "For Instagram, WhatsApp and your website chat." },
  { value: `${number.format(FREE.aiCredits)} AI credits`, label: "Every month on the Free plan." },
  { value: `${number.format(FREE.automations)} automations`, label: "Comment and DM automations on the Free plan." },
  { value: "Official Meta APIs", label: "We never ask for your Instagram or Facebook password." },
];

export function Strip() {
  return (
    <section className="strip" aria-label="The product in numbers">
      <ul className="wrap strip-in">
        {STRIP.map((item) => (
          <li key={item.value}>
            <b>{item.value}</b>
            {item.label}
          </li>
        ))}
      </ul>
    </section>
  );
}
