import { ScrollBox } from "@/components/site/ScrollBox";
import Link from "next/link";

import { LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { LEGAL } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";
import { THEME_COOKIE } from "@/lib/theme";

export const metadata = pageMetadata({
  title: "Cookies and Storage",
  description: `Every cookie and browser storage key ${SITE_NAME} sets, what each one is for and how long it lasts. No analytics or advertising tracking.`,
  path: "/cookies",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

type Row = { name: string; setBy: string; purpose: string; lasts: string };

// C-156: read from the code, not a scanner. Cookies: Clerk's (docs: "How Clerk works" and
// "Cookies"; the app reads __client_uat for the "Open app" hint, C-148), sh_theme (lib/theme.ts).
// Local storage: lib/use-browser-state.ts and lib/use-pane-width.ts keys ("socialhood:…"),
// components/home/checklist-state.ts, lib/push/sync.ts (session storage), the widget's
// sh_visitor_<widget> (api widget/assets/frame.js). The Facebook SDK loads only on "Connect
// WhatsApp" (lib/whatsapp/embedded-signup.ts). Cloudflare's cookie names are the ones Clerk's docs
// and Cloudflare's docs give; Clerk may change them. Update this table when storage changes.
const COOKIES: Row[] = [
  {
    name: "__client",
    setBy: `Clerk, on ${N}'s sign-in domain`,
    purpose: "Keeps you signed in. It can't be read by scripts on the page.",
    lasts: "Long-lived, until you sign out (your browser may limit it)",
  },
  {
    name: "__session (and __session_…)",
    setBy: "Clerk",
    purpose: "A short-lived sign-in token the app sends to our API to prove who you are.",
    lasts: "About 60 seconds, renewed while you use the app",
  },
  {
    name: "__client_uat (and __client_uat_…)",
    setBy: "Clerk",
    purpose: "When you last signed in or out. The website reads it only to show “Open app” instead of “Sign in”.",
    lasts: "Until you sign out",
  },
  {
    name: "__cf_bm, _cfuvid",
    setBy: "Cloudflare, for Clerk, on Clerk's domains",
    purpose: "Bot and abuse protection for sign-up and sign-in, including the Cloudflare Turnstile check.",
    lasts: "From 30 minutes to the end of your browser session",
  },
  {
    name: THEME_COOKIE,
    setBy: N,
    purpose: "Remembers whether you chose the dark, light or system theme in the app.",
    lasts: "1 year",
  },
];

const STORAGE: Row[] = [
  {
    name: "socialhood:pane-width:…",
    setBy: `${N} app (local storage)`,
    purpose: "The widths you drag the inbox and Ask panes to.",
    lasts: "Until you clear your browser's site data",
  },
  {
    name: "socialhood:sidebar-collapsed, socialhood:inbox-details, socialhood:schedule-view",
    setBy: `${N} app (local storage)`,
    purpose: "Whether the sidebar is collapsed, whether conversation details are open, and your calendar view.",
    lasts: "Until you clear your browser's site data",
  },
  {
    name: "socialhood:inbox-shortcuts",
    setBy: `${N} app (local storage)`,
    purpose: "Whether single-key inbox shortcuts are on.",
    lasts: "Until you clear your browser's site data",
  },
  {
    name: "socialhood:get-alerts-dismissed, socialhood:install-dismissed",
    setBy: `${N} app (local storage)`,
    purpose: "That you dismissed the notifications or install prompt, so it doesn't come back.",
    lasts: "Until you clear your browser's site data",
  },
  {
    name: "socialhood:checklist-all-set:…",
    setBy: `${N} app (local and session storage)`,
    purpose: "That the “You're all set” checklist message was shown, per workspace.",
    lasts: "Until you clear your browser's site data, or the tab closes",
  },
  {
    name: "socialhood:push-synced",
    setBy: `${N} app (session storage)`,
    purpose: "That this browser's notification subscription is already registered.",
    lasts: "Until the tab closes",
  },
  {
    name: "sh_visitor_…",
    setBy: `${N} website chat (local storage, in the chat window on a business's website)`,
    purpose: "A random visitor ID, so a visitor's conversation continues on their next visit.",
    lasts: "Until the visitor clears their browser's site data",
  },
  {
    name: "Service worker",
    setBy: `${N} app`,
    purpose: "A small script your browser keeps if you install the app or turn on notifications, to show them.",
    lasts: "Until you turn notifications off or remove the site's data",
  },
];

function Table({ rows, caption }: { rows: Row[]; caption: string }) {
  return (
    <ScrollBox label={caption}>
      <table>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Set by</th>
            <th scope="col">What it&apos;s for</th>
            <th scope="col">How long</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <td>
                <code>{row.name}</code>
              </td>
              <td>{row.setBy}</td>
              <td>{row.purpose}</td>
              <td>{row.lasts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollBox>
  );
}

function sections(): LegalSection[] {
  return [
    {
      id: "no-tracking",
      title: "No tracking, so no banner",
      body: (
        <>
          <p>
            {N} uses only the cookies and storage it needs to work: to sign you in, keep you safe and remember choices you
            make. We don&apos;t use analytics, advertising or tracking cookies, and we don&apos;t load third-party analytics
            or ad scripts. That is why there is no cookie banner: the law doesn&apos;t ask for consent to storage that is
            strictly necessary for a service you asked for.
          </p>
          <p>
            The public website sets no cookies of its own. If you&apos;re signed in to the app, the website can see
            Clerk&apos;s sign-in cookie, which it uses only to show &quot;Open app&quot;.
          </p>
        </>
      ),
    },
    {
      id: "cookies",
      title: "Cookies",
      body: <Table rows={COOKIES} caption="Cookies set when you use Amplychat" />,
    },
    {
      id: "storage",
      title: "Local storage and other browser storage",
      body: (
        <>
          <p>These stay in your browser. We don&apos;t send them to our servers, except where the table says so.</p>
          <Table rows={STORAGE} caption="Browser storage used by Amplychat" />
        </>
      ),
    },
    {
      id: "third-party",
      title: "Meta's sign-up window",
      body: (
        <p>
          When you click Connect WhatsApp, the app loads Meta&apos;s JavaScript SDK to open Meta&apos;s sign-up window. It
          isn&apos;t loaded anywhere else. Meta&apos;s cookies and its{" "}
          <a href="https://www.facebook.com/privacy/policy/" rel="noopener noreferrer">
            privacy policy
          </a>{" "}
          apply to that window, and Meta&apos;s SDK may tell Meta that it was used.
        </p>
      ),
    },
    {
      id: "control",
      title: "Your choices",
      body: (
        <>
          <p>
            You can block or delete cookies and site data in your browser&apos;s settings. If you block Clerk&apos;s cookies
            you can&apos;t sign in; the other items only remember preferences, and the app works without them.
          </p>
          <p>
            If we ever add analytics or advertising cookies, we&apos;ll ask first, update this page and its date, and honour
            Global Privacy Control. Questions: {mail}. More on how we handle data is in our{" "}
            <Link href="/privacy">Privacy Policy</Link>.
          </p>
        </>
      ),
    },
  ];
}

export default function CookiesPage() {
  return (
    <LegalPage
      document="cookies"
      sections={sections()}
      summary={
        <p>
          {N} sets only the cookies and storage it needs to sign you in and remember your choices.{" "}
          <strong>No analytics, no advertising, no tracking</strong>, so there is no cookie banner. Every item is listed
          below.
        </p>
      }
    />
  );
}
