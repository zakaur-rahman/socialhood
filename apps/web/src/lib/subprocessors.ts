/**
 * The one list of the service providers that process personal data for Amplychat (C-156). The
 * subprocessors page renders it in full, the privacy policy links to it, and the DPA's Annex 3 points
 * to it, so there is one source of truth. Change it here, bump `LEGAL_DOCUMENTS.subprocessors`'s
 * date, and email customers before a new provider starts (the DPA's notice promise).
 *
 * Grounded in the code and infra, not the providers' marketing: infra/vm (C-145: one GCP VM in
 * asia-southeast1 runs the site, API, Postgres, Valkey and the nightly backups), ai/gemini.py (the
 * Gemini Developer API with an API key, not Vertex AI), media/cloudinary.py, Clerk (web auth),
 * Resend (email), Sentry (optional, off until a DSN is set: C-149), Dodo (merchant of record,
 * billing off: C-149). Locations are each provider's default region, not read from our dashboards;
 * the owner should confirm them (C-144, C-156). Not reviewed by a lawyer.
 */

export type Subprocessor = {
  name: string;
  purpose: string;
  data: string;
  location: string;
  /** The provider's data processing terms, or its privacy policy when no public DPA page exists. */
  terms: { label: string; href: string };
  /** A short note shown under the purpose, e.g. "Only when error tracking is on". */
  note?: string;
};

export const SUBPROCESSORS: readonly Subprocessor[] = [
  {
    name: "Google Cloud",
    purpose: "Hosts the website, the app, our API, database and background jobs, and our database backups",
    data: "All data in the service",
    location: "Singapore (asia-southeast1)",
    terms: { label: "Cloud Data Processing Addendum", href: "https://cloud.google.com/terms/data-processing-addendum" },
  },
  {
    name: "Google (Gemini API)",
    purpose: "AI features: message and comment analysis, suggested and automatic replies, summaries, captions and Ask",
    data: "The text an AI task needs: messages, comments, knowledge base passages and questions",
    location: "Any country where Google or its agents have facilities (Google may store data briefly or cache it there)",
    terms: { label: "Gemini API terms", href: "https://ai.google.dev/gemini-api/terms" },
  },
  {
    name: "Clerk",
    purpose: "Sign-up, sign-in and sessions, with bot protection by Cloudflare",
    data: "Name, email address, profile photo, sign-in activity and IP address",
    location: "United States",
    terms: { label: "Clerk DPA", href: "https://clerk.com/legal/dpa" },
  },
  {
    name: "Cloudinary",
    purpose: "Stores and delivers photos, videos and files",
    data: "Photos, videos and files you upload, and those received or sent in messages",
    location: "United States, with a worldwide delivery network",
    terms: { label: "Cloudinary privacy policy", href: "https://cloudinary.com/privacy" },
  },
  {
    name: "Resend",
    purpose: "Sends our emails: invitations, notifications and the weekly digest",
    data: "Email addresses and the content of those emails",
    location: "United States",
    terms: { label: "Resend DPA", href: "https://resend.com/legal/dpa" },
  },
  {
    name: "Sentry",
    purpose: "Error tracking",
    data: "Technical error reports, with message text, email addresses, tokens, cookies and request bodies removed before they are sent",
    location: "United States",
    terms: { label: "Sentry DPA", href: "https://sentry.io/legal/dpa/" },
    note: "Only while error tracking is turned on.",
  },
];
