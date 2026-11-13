/**
 * Landing-page analytics (C-194): Umami Cloud, cookieless, on the public site only. The script
 * stores nothing in the browser and builds no visitor profile, so there is still no cookie banner.
 * The website ID is public by design (it is in every page's HTML). Umami counts only on
 * UMAMI_DOMAINS, so the dashboard, local runs, CI and e2e send nothing.
 */
export const UMAMI_SCRIPT = "https://cloud.umami.is/script.js";
export const UMAMI_WEBSITE_ID = "c47e3ef4-5078-49b2-9237-d50980ff952b";
export const UMAMI_DOMAINS = "amplychat.com";
/** Where the script sends its counts (Umami Cloud's collector), for the CSP. */
export const UMAMI_COLLECTOR = "https://gateway.umami.is";

/** A sign-up button's click, counted as a goal with the page it was on. */
export const START_FREE_EVENT = "start_free";

/** The goal a call to action counts, if any: every link into sign-up is a "Start free" click. */
export function ctaEvent(href: string): string | undefined {
  return /\/sign-up(\?|$)/.test(href) ? START_FREE_EVENT : undefined;
}
