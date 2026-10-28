import { BadgeCheck, KeyRound, Layers, LockKeyhole, Trash2, type LucideIcon } from "lucide-react";
import Link from "next/link";

// Only what is true of the built system (product guide, "Security and privacy"). No certifications,
// uptime figures or compliance badges: we have none to claim.
export const TRUST_POINTS: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: BadgeCheck, title: "Official Meta APIs", body: "Instagram and WhatsApp connect through Meta's official, approved APIs." },
  { icon: KeyRound, title: "No passwords asked", body: "Amplychat never asks for, or sees, your Instagram or Facebook password." },
  { icon: LockKeyhole, title: "Encrypted tokens", body: "The access tokens that let Amplychat act for your accounts are stored encrypted." },
  { icon: Layers, title: "Your workspace stays separate", body: "Every workspace's data is kept separate from every other workspace." },
  {
    icon: Trash2,
    title: "Delete anytime",
    body: "Disconnect an account whenever you like. When you delete your workspace, its data, including uploaded media, is permanently removed within 24 hours.",
  },
];

/** Security and privacy, on a night band (C-155). */
export function Trust() {
  return (
    <section className="sec night" id="security" aria-labelledby="trust-title">
      <div className="wrap">
        <div className="split-head">
          <div>
            <p className="kicker">Security and privacy</p>
            <h2 id="trust-title" className="h2">
              Your customers&apos; messages, handled with care
            </h2>
          </div>
          <p className="lede">
            Read exactly what we collect and why in our <Link href="/privacy">Privacy Policy</Link>.
          </p>
        </div>
        <ul className="trust-grid">
          {TRUST_POINTS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="tr">
              <span className="ic" aria-hidden>
                <Icon className="size-5" strokeWidth={1.8} />
              </span>
              <div>
                <h3>{title}</h3>
                <p>{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
