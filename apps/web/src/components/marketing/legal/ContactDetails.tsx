import { LEGAL, grievanceDays, isSet, operatorName, telHref, type LegalConfig } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";
import { READING } from "@/styles/tokens";

import { LegalFacts } from "./LegalPage";

const N = SITE_NAME;
const LINK = "font-medium text-brand-fg underline underline-offset-4";
const HEADING = "text-xl font-semibold tracking-tight text-fg";

/**
 * C-144: the "About us" and "Contact us" page payment providers and Meta look for: the business's
 * name and type, the proprietor, the email, and the phone and address once the owner sets them in
 * lib/legal.ts (nothing is shown for an unset one).
 */
export function ContactDetails({ config = LEGAL }: { config?: LegalConfig }) {
  const operator = operatorName(config);
  const phone = isSet(config.phone) ? config.phone.trim() : null;
  return (
    <>
      <section aria-labelledby="about" className="mt-10">
        <h2 id="about" className={HEADING}>
          About us
        </h2>
        <p className={cn(READING, "mt-3 text-fg-secondary")}>
          {N} is made and run by {operator}
          {isSet(config.entityType) ? <>, a {config.entityType.trim().replace(/^./, (c) => c.toLowerCase())}</> : null}
          {isSet(config.proprietor) ? <>, owned by {config.proprietor.trim()}</> : null}. It gives businesses one inbox for
          Instagram, WhatsApp, Facebook and website chat, with AI that drafts replies from each business&apos;s own
          knowledge, and automations for comments and messages.
        </p>
        <LegalFacts config={config} />
      </section>

      <section aria-labelledby="reach-us" className="mt-10">
        <h2 id="reach-us" className={HEADING}>
          How to reach us
        </h2>
        <ul className={cn(READING, "mt-3 list-disc space-y-2 pl-5 text-fg-secondary")}>
          <li>
            <strong className="text-fg">Email</strong>:{" "}
            <a href={`mailto:${config.contactEmail}`} className={LINK}>
              {config.contactEmail}
            </a>
            , for support, billing, privacy requests and anything else.
            {isSet(config.supportResponseTime) ? <> We reply {config.supportResponseTime.trim()}.</> : null}
          </li>
          {phone ? (
            <li>
              <strong className="text-fg">Phone</strong>:{" "}
              <a href={telHref(phone)} className={LINK}>
                {phone}
              </a>
            </li>
          ) : null}
          <li>
            <strong className="text-fg">Privacy grievances</strong>: email us with &quot;Grievance&quot; in the subject. We
            answer within {grievanceDays(config)} days.
          </li>
        </ul>
      </section>
    </>
  );
}
