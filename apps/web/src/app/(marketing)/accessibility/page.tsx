import Link from "next/link";

import { LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { LEGAL } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Accessibility Statement",
  description: `How accessible ${SITE_NAME} is: the standard we aim for, how we test, the limits we know about and how to report a problem.`,
  path: "/accessibility",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}?subject=Accessibility`}>{email}</a>;

/** C-156: the reply target the owner can keep alone. Change it here if that changes. */
const REPLY_WORKING_DAYS = 5;

// C-156: an honest statement, not a conformance claim. Testing: axe (@axe-core/playwright) in the
// UI screenshot run at 375 and 1280 px (scripts/ui-shots), keyboard checks from the accessibility
// audit (docs/ui-audit/ACCESSIBILITY.md) and the UI programme. Known limits come from the code:
// customer media arrives with no descriptions and voice notes aren't transcribed
// (components/inbox/AttachmentView.tsx); Meta's sign-in and sign-up windows, Clerk's sign-in form,
// Cloudflare's bot check and the payment checkout are third-party; the chat widget sits on pages
// businesses control. No audit by an outside auditor has been done.
function sections(): LegalSection[] {
  return [
    {
      id: "aim",
      title: "What we aim for",
      body: (
        <>
          <p>
            We want everyone to be able to use {N}, including people who use a keyboard, a screen reader, magnification,
            voice control or reduced motion. We aim to meet the{" "}
            <a href="https://www.w3.org/TR/WCAG22/" rel="noopener noreferrer">
              Web Content Accessibility Guidelines (WCAG) 2.2
            </a>{" "}
            at level AA on this website and in the app.
          </p>
          <p>
            That is a goal, not a certificate. No outside auditor has checked {N}, and we don&apos;t claim full
            conformance.
          </p>
        </>
      ),
    },
    {
      id: "testing",
      title: "How we test",
      body: (
        <ul>
          <li>
            Automated checks with axe, the open-source accessibility engine, on our main screens at phone and desktop
            widths.
          </li>
          <li>
            Keyboard checks: every flow should work without a mouse, with a visible focus indicator and a skip link to the
            main content.
          </li>
          <li>
            Design rules we build with: text and controls with enough contrast in both the light and dark themes, touch
            targets sized for phones, reduced motion respected, and charts that come with a text table for screen
            readers.
          </li>
        </ul>
      ),
    },
    {
      id: "limits",
      title: "Known limits",
      body: (
        <>
          <p>These are the gaps we know about:</p>
          <ul>
            <li>
              <strong>What other people send.</strong> Photos, videos and voice notes that customers send arrive from
              Instagram, Facebook and WhatsApp without descriptions or captions. {N} labels them with their type and sender,
              but can&apos;t describe them, and voice notes aren&apos;t transcribed.
            </li>
            <li>
              <strong>Screens we don&apos;t control.</strong> Meta&apos;s windows for connecting Instagram, Facebook and
              WhatsApp, the sign-in form and bot check our sign-in provider shows, and the payment checkout come from other
              companies. We choose providers that care about accessibility, but we can&apos;t fix their screens.
            </li>
            <li>
              <strong>Website chat on other sites.</strong> The chat window is ours, but the page around it belongs to the
              business that adds it.
            </li>
            <li>
              <strong>Dragging.</strong> Cropping a photo and placing tags use dragging; both also work with the arrow keys.
              If you find any other place that needs dragging, tell us.
            </li>
          </ul>
          <p>We fix accessibility problems as part of our normal work, starting with the ones that block someone.</p>
        </>
      ),
    },
    {
      id: "report",
      title: "Report a problem",
      body: (
        <>
          <p>
            If something on {N} is hard or impossible for you to use, email {mail}. Tell us the page or screen, what you
            were trying to do, and the browser and any assistive technology you use. Screenshots help but aren&apos;t
            needed.
          </p>
          <p>
            We reply within {REPLY_WORKING_DAYS} working days. If we can&apos;t fix the problem quickly, we&apos;ll tell
            you when we expect to, and help you do what you needed another way in the meantime.
          </p>
        </>
      ),
    },
    {
      id: "more",
      title: "More information",
      body: (
        <p>
          Our <Link href="/privacy">Privacy Policy</Link> explains how we handle what you send us, and our{" "}
          <Link href="/contact">contact page</Link> lists every way to reach us.
        </p>
      ),
    },
  ];
}

export default function AccessibilityPage() {
  return (
    <LegalPage
      document="accessibility"
      sections={sections()}
      summary={
        <p>
          We aim for WCAG 2.2 level AA and test with axe and the keyboard. This page lists the limits we know about. If
          something doesn&apos;t work for you, email {mail} and we reply within {REPLY_WORKING_DAYS} working days.
        </p>
      }
    />
  );
}
