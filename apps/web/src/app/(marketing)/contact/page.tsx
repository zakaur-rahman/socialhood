import { ArrowRight, CircleHelp, Code, type LucideIcon, ShieldCheck, Tag, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { InfoBand, InfoPage } from "@/components/marketing/InfoPage";
import { Ico } from "@/components/marketing/landing/Ico";
import { ContactDetails } from "@/components/marketing/legal/ContactDetails";
import { FAQ_PATH } from "@/lib/marketing/faq";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Contact us",
  description: `Who runs ${SITE_NAME} and how to reach us: email, support, privacy requests and grievances.`,
  path: "/contact",
});

const N = SITE_NAME;

const HELP_LINKS: { label: string; href: string; note: string; icon: LucideIcon }[] = [
  { label: "Frequently asked questions", href: FAQ_PATH, note: `Common questions about ${SITE_NAME}`, icon: CircleHelp },
  { label: "Plans and limits", href: "/pricing", note: "What each plan includes and costs", icon: Tag },
  { label: "Data deletion", href: "/data-deletion", note: "Delete your data, or check a request from Instagram", icon: Trash2 },
  { label: "Developers", href: "/developers/api", note: "The public API, webhooks and Zapier", icon: Code },
  { label: "Privacy Policy", href: "/privacy", note: "Your rights and how to raise a grievance", icon: ShieldCheck },
];

/** /contact (C-144; C-159 layout): contact cards, about us with the facts, and where to find answers. */
export default function ContactPage() {
  return (
    <InfoPage
      name="Contact us"
      path="/contact"
      className="contact"
      eyebrow="Contact"
      title="Contact us"
      lede={`Questions about ${N}, your plan or your data? Write to us and a person will answer.`}
    >
      <ContactDetails />

      <InfoBand id="help" title="Find an answer" wide>
        <ul className="fgrid tgrid-3">
          {HELP_LINKS.map((link) => (
            <li key={link.href} className="fcard is-link">
              <Ico icon={link.icon} />
              <h3>
                <Link href={link.href as Route} className="fcard-link">
                  {link.label}
                  <ArrowRight size={16} strokeWidth={1.75} aria-hidden focusable="false" className="fcard-arrow" />
                </Link>
              </h3>
              <p>{link.note}</p>
            </li>
          ))}
        </ul>
      </InfoBand>
    </InfoPage>
  );
}
