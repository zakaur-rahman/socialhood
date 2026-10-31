import { Mail, MapPin, Phone, Scale } from "lucide-react";

import { InfoBand, InfoCard } from "@/components/marketing/InfoPage";
import { LEGAL, grievanceDays, isSet, operatorName, telHref, type LegalConfig } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";

import { LegalFacts } from "./LegalPage";

const N = SITE_NAME;

/**
 * C-144: the "About us" and "Contact us" page payment providers and Meta look for: the business's
 * name and type, the proprietor, the email, and the phone and address once the owner sets them in
 * lib/legal.ts (nothing is shown for an unset one). C-159: the ways to reach us as contact cards,
 * then "About us" beside the facts.
 */
export function ContactDetails({ config = LEGAL }: { config?: LegalConfig }) {
  const operator = operatorName(config);
  const phone = isSet(config.phone) ? config.phone.trim() : null;
  const place = isSet(config.registeredAddress)
    ? { label: "Registered address", value: config.registeredAddress.trim() }
    : isSet(config.publicLocation)
      ? { label: "Location", value: config.publicLocation.trim() }
      : null;
  const officer = config.grievanceOfficer;
  const officerWho = officer ? [officer.name, officer.role].find(isSet)?.trim() : undefined;
  return (
    <>
      <InfoBand id="reach-us" title="How to reach us" wide className="contact-reach">
        <ul className="fgrid tgrid-3 contact-cards">
          <InfoCard icon={Mail} title="Email">
            <p>
              <a href={`mailto:${config.contactEmail}`} className="contact-v">
                {config.contactEmail}
              </a>
            </p>
            <p>
              For support, billing, privacy requests and anything else.
              {isSet(config.supportResponseTime) ? <> We reply {config.supportResponseTime.trim()}.</> : null}
            </p>
          </InfoCard>
          {phone ? (
            <InfoCard icon={Phone} title="Phone">
              <p>
                <a href={telHref(phone)} className="contact-v">
                  {phone}
                </a>
              </p>
            </InfoCard>
          ) : null}
          <InfoCard icon={Scale} title="Privacy grievances">
            {officerWho ? <p className="contact-v">{officerWho}</p> : null}
            <p>
              Email us with &quot;Grievance&quot; in the subject. We answer within {grievanceDays(config)} days.
            </p>
          </InfoCard>
          {place ? (
            <InfoCard icon={MapPin} title={place.label}>
              <p className="contact-v">{place.value}</p>
            </InfoCard>
          ) : null}
        </ul>
      </InfoBand>

      <InfoBand
        id="about"
        title="About us"
        intro={
          <p>
            {N} is made and run by {operator}
            {isSet(config.entityType) ? <>, a {config.entityType.trim().replace(/^./, (c) => c.toLowerCase())}</> : null}
            {isSet(config.proprietor) ? <>, owned by {config.proprietor.trim()}</> : null}. It gives businesses one inbox for
            Instagram, WhatsApp, Facebook and website chat, with AI that drafts replies from each business&apos;s own
            knowledge, and automations for comments and messages.
          </p>
        }
      >
        <LegalFacts config={config} />
      </InfoBand>
    </>
  );
}
