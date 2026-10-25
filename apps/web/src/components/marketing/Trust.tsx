import { BadgeCheck, KeyRound, Layers, LockKeyhole, Trash2, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { MARKETING_HEADING } from "@/styles/tokens";
import { cn } from "@/lib/utils";

import { Container, SECTION_EYEBROW } from "./primitives";

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
    <section aria-labelledby="trust-title" className="border-t border-line-subtle bg-panel-glass py-16 sm:py-20">
      <Container className="grid gap-10 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-14">
        <div className="text-center lg:text-left">
          <p className={SECTION_EYEBROW}>Security and privacy</p>
          <h2 id="trust-title" className={cn(MARKETING_HEADING, "mt-3 text-balance")}>
            Your customers&apos; messages, handled with care
          </h2>
          <p className="mt-4 text-base leading-relaxed text-pretty text-fg-secondary">
            Read exactly what we collect and why in our{" "}
            <Link href="/privacy" className="font-medium text-brand-fg underline underline-offset-4">
              Privacy Policy
            </Link>
            .
          </p>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2">
          {POINTS.map(({ icon: Icon, title, body }, index) => (
            <li key={title} data-reveal style={{ "--reveal-delay": `${(index % 2) * 80}ms` } as CSSProperties} className={index === POINTS.length - 1 ? "sm:col-span-2" : undefined}>
              <div className="flex h-full gap-3.5 rounded-2xl border border-line bg-canvas p-4 transition-colors duration-slow hover:border-line-strong">
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand-fg">
                  <Icon className="size-4.5" aria-hidden />
                </span>
                <div>
                  <h3 className="text-sm font-semibold">{title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-fg-secondary">{body}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
