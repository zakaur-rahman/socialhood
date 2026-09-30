import { BadgeCheck, KeyRound, Layers, LockKeyhole, Trash2, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { Container, SectionHeading } from "./primitives";

// Only what is true of the built system (product guide, "Security and privacy"). No certifications,
// uptime figures or compliance badges: we have none to claim.
const POINTS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: BadgeCheck,
    title: "Official Meta APIs",
    body: "Instagram and WhatsApp connect through Meta's official, approved APIs.",
  },
  {
    icon: KeyRound,
    title: "No passwords asked",
    body: "Social Hood never asks for, or sees, your Instagram or Facebook password.",
  },
  {
    icon: LockKeyhole,
    title: "Encrypted tokens",
    body: "The access tokens that let Social Hood act for your accounts are stored encrypted.",
  },
  {
    icon: Layers,
    title: "Your workspace stays separate",
    body: "Every workspace's data is kept separate from every other workspace.",
  },
  {
    icon: Trash2,
    title: "Delete anytime",
    body: "Disconnect an account whenever you like. When you delete your workspace, its data, including uploaded media, is permanently removed within 24 hours.",
  },
];

export function Trust() {
  return (
    <section aria-labelledby="trust-title" className="border-t border-line-subtle bg-panel/40 py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="trust-title"
          eyebrow="Security and privacy"
          title="Your customers' messages, handled with care"
          intro={
            <>
              Read exactly what we collect and why in our{" "}
              <Link href="/privacy" className="font-medium text-brand-fg underline underline-offset-4">
                Privacy Policy
              </Link>
              .
            </>
          }
        />
        <ul className="mx-auto mt-14 grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {POINTS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex gap-4 rounded-2xl border border-line bg-canvas p-5">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand-fg">
                <Icon className="size-5" aria-hidden />
              </span>
              <div>
                <h3 className="text-sm font-semibold">{title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-fg-secondary">{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
