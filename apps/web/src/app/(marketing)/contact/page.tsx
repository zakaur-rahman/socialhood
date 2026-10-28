import type { Route } from "next";
import Link from "next/link";

import { ContactDetails } from "@/components/marketing/legal/ContactDetails";
import { Container, SECTION_EYEBROW } from "@/components/marketing/primitives";
import { Card } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";
import { cn } from "@/lib/utils";
import { READING } from "@/styles/tokens";

export const metadata = pageMetadata({
  title: "Contact us",
  description: `Who runs ${SITE_NAME} and how to reach us: email, support, privacy requests and grievances.`,
  path: "/contact",
});

const N = SITE_NAME;
const LINK = "font-medium text-brand-fg underline underline-offset-4";
const HEADING = "h-sec";

const HELP_LINKS: { label: string; href: string; note: string }[] = [
  { label: "Frequently asked questions", href: "/#faq", note: `Common questions about ${SITE_NAME}` },
  { label: "Plans and limits", href: "/pricing", note: "What each plan includes and costs" },
  { label: "Data deletion", href: "/data-deletion", note: "Delete your data, or check a request from Instagram" },
  { label: "Developers", href: "/developers", note: "The public API, webhooks and Zapier" },
  { label: "Privacy Policy", href: "/privacy", note: "Your rights and how to raise a grievance" },
];

export default function ContactPage() {
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <Container className="max-w-3xl py-12 sm:py-16">
        <p className={SECTION_EYEBROW}>Contact</p>
        <h1 className={"h-page"}>Contact us</h1>
        <p className={cn(READING, "mt-4 text-fg-secondary")}>
          Questions about {N}, your plan or your data? Write to us and a person will answer.
        </p>

        <ContactDetails />

        <section aria-labelledby="help" className="mt-10">
          <h2 id="help" className={HEADING}>
            Find an answer
          </h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {HELP_LINKS.map((link) => (
              <li key={link.href}>
                <Card className="h-full">
                  <Link href={link.href as Route} className={cn(LINK, "text-sm")}>
                    {link.label}
                  </Link>
                  <p className="mt-1 text-sm text-fg-secondary">{link.note}</p>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      </Container>
    </main>
  );
}
