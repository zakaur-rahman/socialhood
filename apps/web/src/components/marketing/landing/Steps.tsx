import { BookOpenText, Link2, type LucideIcon, MessageSquareReply } from "lucide-react";

/** The three setup steps, as the site has always described them; each with its icon (C-157 motion), shown on the feature pages (GtmPageView). */
export const SETUP_STEPS: { title: string; body: string; icon: LucideIcon }[] = [
  {
    title: "Connect your accounts",
    icon: Link2,
    body: "Connect your Instagram professional account with Instagram's own login, and your WhatsApp Business number through Meta's official setup. Amplychat never asks for your password.",
  },
  {
    title: "Add your knowledge",
    icon: BookOpenText,
    body: "Prices, products, delivery, returns, timings and FAQs, as text, a link or a file. Test a question to see how the AI would answer before customers ask.",
  },
  {
    title: "Let the AI draft or reply",
    icon: MessageSquareReply,
    body: "Start with Suggest and send the drafts you like. On Creator or Business, switch an account to Auto: the AI replies when it's confident and hands everything else to you.",
  },
];

/**
 * Set up in three steps (C-157): the last word before the FAQ, on a night band. The order is the list's
 * own (an <ol>), with no step numbers or icon tiles on screen (the design audit, 2026-11-06).
 */
export function Steps() {
  return (
    <section className="sec night setup" id="setup" aria-labelledby="setup-title">
      <div className="wrap">
        <h2 id="setup-title" className="h2-sm">
          Set up in three steps
        </h2>
        <ol className="steps after-head">
          {SETUP_STEPS.map((step) => (
            <li key={step.title}>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
