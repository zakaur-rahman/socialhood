import Link from "next/link";

// Only what is true of the built system (product guide, "Security and privacy"). No certifications,
// uptime figures or compliance badges: we have none to claim. C-157: the points that aren't said
// elsewhere on the page lead, and the section sits early, right after the modes.
export const TRUST_POINTS: { title: string; body: string }[] = [
  { title: "No passwords asked", body: "Amplychat never asks for, or sees, your Instagram or Facebook password." },
  { title: "Encrypted tokens", body: "The access tokens that let Amplychat act for your accounts are stored encrypted." },
  { title: "Your workspace stays separate", body: "Every workspace's data is kept separate from every other workspace." },
  {
    title: "Delete anytime",
    body: "Disconnect an account whenever you like. When you delete your workspace, its data, including uploaded media, is permanently removed within 24 hours.",
  },
  { title: "Official Meta APIs", body: "Instagram and WhatsApp connect through Meta's official, approved APIs." },
];

/**
 * Security and privacy, on a night band (C-155): a spec list, no icons (C-157). The heading block on
 * the left (it stays in view on a wide screen), the five points on the right as rows: the title in a
 * fixed column, its description beside it, a hairline between rows.
 */
export function Trust() {
  return (
    <section className="sec night spec-sec" id="security" aria-labelledby="trust-title">
      <div className="wrap spec">
        <div className="spec-head">
          <h2 id="trust-title" className="h2">
            Your customers&apos; messages, handled with care
          </h2>
          <p className="lede">
            Read exactly what we collect and why in our <Link href="/privacy">Privacy Policy</Link>, and how we protect it on
            our <Link href="/security">security page</Link>.
          </p>
        </div>
        <ul className="spec-list">
          {TRUST_POINTS.map(({ title, body }) => (
            <li key={title} className="spec-row">
              <h3>{title}</h3>
              <p>{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
