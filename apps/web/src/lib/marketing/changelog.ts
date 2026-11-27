/**
 * "What's new" (/changelog, C-156): what has shipped, newest first, in words a customer reads.
 * Built from the merged pull requests on develop (#13 to #238) and their CONFLICTS entries; only
 * features a customer can use or see, no infrastructure, tests or design-system work. A feature
 * that waits on Meta or a listing says so in `status`.
 *
 * To add an entry: put it at the top with the date it merged (ISO), a short title, its area and one
 * or two plain sentences. The page groups entries by month.
 */
import { SITE_NAME } from "./site";

export const CHANGELOG_PATH = "/changelog";

/** What part of the product an entry is about (C-159): the page shows it as a label with an icon. */
export type ChangelogArea = "inbox" | "ai" | "automations" | "publishing" | "commerce" | "team" | "website" | "app";

export const CHANGELOG_AREAS: Record<ChangelogArea, string> = {
  inbox: "Inbox",
  ai: "AI",
  automations: "Automations",
  publishing: "Publishing",
  commerce: "Selling",
  team: "Team",
  website: "Website",
  app: "App",
};

export type ChangelogEntry = {
  /** When it shipped (merged to develop), as an ISO date. */
  date: string;
  title: string;
  area: ChangelogArea;
  body: string;
  /** What it still waits for, when it can't be used by everyone yet. */
  status?: string;
  /** The pull request(s), for us; not shown on the page. */
  prs: number[];
};

export const CHANGELOG: ChangelogEntry[] = [
  {
    date: "2026-11-27",
    title: "More Instagram accounts on Creator and Business",
    area: "app",
    body: "Creator now connects 3 Instagram accounts and Business 6, at the same prices.",
    prs: [278],
  },
  {
    date: "2026-11-14",
    title: "YouTube videos and Shorts",
    area: "publishing",
    body: "Connect a YouTube channel and schedule videos and Shorts from the composer or from your AI app. A video for YouTube alone goes straight to YouTube, without our file size limit.",
    status: "Opens to everyone after Google's review",
    prs: [238],
  },
  {
    date: "2026-11-13",
    title: "Schedule from 1 minute ahead",
    area: "publishing",
    body: "Posts and messages can be scheduled for 1 minute from now, and the time list no longer offers times that have passed.",
    prs: [224],
  },
  {
    date: "2026-11-13",
    title: "Publish now and switch automations from AI apps",
    area: "ai",
    body: "Your AI app can publish a post right away and turn an automation on or off. Each one shows you a preview and waits for your yes, and owners and admins are told.",
    prs: [234],
  },
  {
    date: "2026-11-13",
    title: "More Instagram accounts on paid plans",
    area: "app",
    body: "Creator now connects 2 Instagram accounts, Business 4 and Agency 10. Website chat runs on 1 site on Free and Creator, 3 on Business and 20 on Agency.",
    prs: [235],
  },
  {
    date: "2026-11-13",
    title: "See which account a conversation is on",
    area: "inbox",
    body: "With several accounts on one platform, each conversation shows its account, and the account filter shows each account's picture.",
    prs: [235],
  },
  {
    date: "2026-11-13",
    title: "A clearer AI menu in the Human Agent window",
    area: "inbox",
    body: "When a conversation is in Meta's Human Agent window, the AI menu explains that only replies you send go out.",
    prs: [225],
  },
  {
    date: "2026-11-13",
    title: "A warmer website",
    area: "website",
    body: "The public site has a warmer sand and charcoal look.",
    prs: [227],
  },
  {
    date: "2026-11-12",
    title: "A redesigned website chat",
    area: "website",
    body: "The chat on your website looks cleaner: a flat panel, joined message bubbles and a round Send button.",
    prs: [230],
  },
  {
    date: "2026-11-07",
    title: "Human Agent replies are always yours",
    area: "inbox",
    body: "After 24 hours, an AI draft goes into the reply box for you to check and send, as Meta's Human Agent rules require, instead of going out in one click.",
    prs: [221],
  },
  {
    date: "2026-11-06",
    title: "A calmer app",
    area: "app",
    body: "A plainer look across the app, with page headers and search rows that stay in view as you scroll.",
    prs: [214, 215, 217],
  },
  {
    date: "2026-11-05",
    title: "Tighter access and approvals",
    area: "team",
    body: "Only owners and admins can mark orders paid or refund them. Auto replies need a source in your knowledge, and anything without one goes to a person.",
    prs: [212],
  },
  {
    date: "2026-11-05",
    title: "An animated product demo",
    area: "website",
    body: "The landing page shows the inbox, AI drafts and automations at work.",
    prs: [208, 219],
  },
  {
    date: "2026-11-03",
    title: "Four plans and six-month billing",
    area: "app",
    body: "Free, Creator at $15, Business at $30 and Agency at $70 a month. Paying every six months saves 10% on Creator, 15% on Business and 25% on Agency.",
    status: "Paid plans aren't on sale yet",
    prs: [203, 206, 209, 210],
  },
  {
    date: "2026-11-01",
    title: "Usage and billing tabs",
    area: "app",
    body: "Settings › Billing and usage opens on what you've used this month, with billing in its own tab.",
    prs: [202],
  },
  {
    date: "2026-11-01",
    title: "Automations and posts from AI apps",
    area: "ai",
    body: "Ask Claude or ChatGPT to set up a comment automation or an Instagram post. It shows you a preview before anything is saved.",
    prs: [200],
  },
  {
    date: "2026-11-01",
    title: "Safer API keys",
    area: "app",
    body: "API keys can expire and be limited to your IP addresses. They're revoked when the person who made them leaves, or at once if GitHub finds one published.",
    prs: [197],
  },
  {
    date: "2026-10-31",
    title: "Connect Claude, ChatGPT and other AI apps",
    area: "ai",
    body: "Work with your inbox, knowledge, automations and posts from your AI app, after you sign in and approve it. API keys are in Settings.",
    prs: [193, 194, 195, 196],
  },
  {
    date: "2026-10-31",
    title: "Feature pages, a glossary and comparisons",
    area: "website",
    body: "Deeper feature and automation pages, a glossary, and a guide to Manychat alternatives.",
    prs: [189, 191],
  },
  {
    date: "2026-10-30",
    title: "A new website",
    area: "website",
    body: "A redesigned public site with a new landing page, how it works and features pages, and new sign-in pages.",
    prs: [178, 186],
  },
  {
    date: "2026-10-28",
    title: "Guides",
    area: "website",
    body: "Practical guides for businesses and creators on Instagram and WhatsApp, with an RSS feed.",
    prs: [174],
  },
  {
    date: "2026-10-28",
    title: "A faster website on phones",
    area: "website",
    body: "Public pages load less code and show their content sooner on mobile.",
    prs: [176, 166],
  },
  {
    date: "2026-10-27",
    title: "The app has its own address",
    area: "app",
    body: "The signed-in app now lives on its own dashboard address, separate from the website.",
    prs: [161],
  },
  {
    date: "2026-10-26",
    title: `Social Hood is now ${SITE_NAME}`,
    area: "app",
    body: "A new name and a new logo. Nothing changes in how the product works.",
    prs: [156],
  },
  {
    date: "2026-10-26",
    title: "Security, privacy and legal pages",
    area: "website",
    body: "A responsible disclosure policy, a privacy policy and terms written for the product, refund and contact pages, and a data deletion page.",
    prs: [159],
  },
  {
    date: "2026-10-25",
    title: "Instagram collaborators, tags and location",
    area: "publishing",
    body: "Invite collaborators to a post or Reel, tag people, add a location and set Reel options when you schedule.",
    prs: [152],
  },
  {
    date: "2026-10-25",
    title: "Contact names your whole team sees",
    area: "inbox",
    body: "Give a contact a name once and everyone in the workspace sees it. Pages load without jumping around.",
    prs: [153],
  },
  {
    date: "2026-10-25",
    title: "Light and dark themes, and a weekly report per account",
    area: "app",
    body: "Choose light, dark or your device's setting. The weekly report can now be read for each account.",
    prs: [148],
  },
  {
    date: "2026-10-25",
    title: "Orders and payment requests",
    area: "commerce",
    body: "Record orders and send a Razorpay payment link or a UPI request in the chat, paid to your own account. Send WhatsApp catalogue messages. Part of Pro.",
    prs: [147],
  },
  {
    date: "2026-10-25",
    title: "Product catalogue, assignment and sequences",
    area: "commerce",
    body: "Add products by hand or CSV so the AI can answer price and stock. Assign conversations by hand or in turn. Send timed follow-ups that stop when the customer replies.",
    prs: [146],
  },
  {
    date: "2026-10-24",
    title: "Team roles, website chat, the public API, Zapier and Google Sheets",
    area: "team",
    body: "Owners, admins and agents. A chat widget for your website in the same inbox. API keys, a Zapier app and Google Sheets sync on Pro. Stories in the publishing calendar. Ask can prepare changes for you to confirm.",
    prs: [145],
  },
  {
    date: "2026-10-24",
    title: "Facebook Pages",
    area: "inbox",
    body: "Messenger chats, Page comments and Page publishing in the same app.",
    status: "With Meta's approval",
    prs: [145],
  },
  {
    date: "2026-10-24",
    title: "Templates, trends and a website crawl",
    area: "automations",
    body: "A new gallery of automation templates. Trends in what customers ask about. Teach the AI by reading your website's pages.",
    prs: [144],
  },
  {
    date: "2026-10-24",
    title: "Data capture, link clicks, saved replies and business hours",
    area: "automations",
    body: "Ask for an email or phone in a flow and record consent. See who clicked a link and where people drop off in a flow. Saved replies, and business hours with an away message.",
    prs: [141],
  },
  {
    date: "2026-10-24",
    title: "The flow editor, contacts and leads",
    area: "automations",
    body: "Build flows with questions, branches and waits, step by step. A contacts page with tags and fields, a leads list, and a welcome message and default reply.",
    prs: [140],
  },
  {
    date: "2026-10-24",
    title: "Story replies, story mentions and conversation starters",
    area: "automations",
    body: "A reply to your story or a story that mentions you can start an automation, and a Mentions page lists them. Ice breakers give people questions to tap.",
    prs: [137, 139],
  },
  {
    date: "2026-10-24",
    title: "Entry links, QR codes, ads and Live comments",
    area: "automations",
    body: "Links and QR codes that open a chat, and triggers for chats that start from an ad and for comments during an Instagram Live.",
    status: "With Meta's approval",
    prs: [138, 139],
  },
  {
    date: "2026-10-23",
    title: "The Activity page",
    area: "automations",
    body: "Every failed send or step, with the reason in plain words, one action to fix it and safe retries.",
    prs: [135],
  },
  {
    date: "2026-10-23",
    title: "Webhooks, contact tags and fields, and where chats start",
    area: "app",
    body: "Send events to your own tools with signed webhooks. Tag contacts, add custom fields and export them as CSV. Each conversation shows how it started.",
    prs: [132, 130, 128],
  },
  {
    date: "2026-10-21",
    title: "A design pass across the whole app",
    area: "app",
    body: "Resizable inbox and Ask panes, pages that fill the screen, clearer labels and better screen reader support.",
    prs: [113, 111, 106, 120],
  },
  {
    date: "2026-10-14",
    title: "Inbox views, keyboard shortcuts and a needs-reply view for comments",
    area: "inbox",
    body: "Views and filters stay in the address, single-key shortcuts you can switch on, and a count of comments that still need a reply on each post.",
    prs: [83, 85, 81],
  },
  {
    date: "2026-09-30",
    title: `Ask ${SITE_NAME}`,
    area: "ai",
    body: "Ask about your own messages, comments and posts in plain words. Answers show the numbers they used and link to their sources. It reads and drafts; it never sends by itself.",
    prs: [],
  },
  {
    date: "2026-09-30",
    title: "Notifications, the weekly email and an installable app",
    area: "app",
    body: "In-app, email and phone push notifications, a summary every Monday, and an app you install from the browser.",
    prs: [],
  },
  {
    date: "2026-09-29",
    title: "Publishing and the calendar",
    area: "publishing",
    body: "Schedule Instagram posts, carousels and Reels on a calendar, with AI captions and hashtag ideas.",
    prs: [],
  },
  {
    date: "2026-09-29",
    title: "Comment intelligence and analytics",
    area: "ai",
    body: "Sentiment, topics and spam for every post's comments, and reports on messages, reply rate and response time.",
    prs: [],
  },
  {
    date: "2026-09-29",
    title: "AI replies from your knowledge",
    area: "ai",
    body: "Add your knowledge, and the AI suggests replies or sends them in Auto mode, hands the hard ones to you and records the questions it couldn't answer.",
    prs: [],
  },
  {
    date: "2026-09-29",
    title: "Comment-to-DM automations",
    area: "automations",
    body: "Send a DM to everyone who comments a keyword, with a tap first and a follow invite after the message.",
    prs: [],
  },
  {
    date: "2026-09-29",
    title: "One inbox for Instagram and WhatsApp",
    area: "inbox",
    body: "Instagram DMs and WhatsApp in one inbox, with files, audio, video and stickers both ways.",
    prs: [],
  },
];

/** The entries grouped by month ("October 2026"), newest month first, in the order written. */
export function changelogByMonth(entries: readonly ChangelogEntry[] = CHANGELOG): { month: string; id: string; entries: ChangelogEntry[] }[] {
  const months = new Map<string, ChangelogEntry[]>();
  for (const entry of [...entries].sort((a, b) => b.date.localeCompare(a.date))) {
    const key = entry.date.slice(0, 7);
    months.set(key, [...(months.get(key) ?? []), entry]);
  }
  return [...months].map(([key, list]) => ({
    id: `m-${key}`,
    month: new Date(`${key}-01T00:00:00Z`).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" }),
    entries: list,
  }));
}

/** The newest entry's date: the page's "last updated" in the sitemap. */
export function changelogUpdated(entries: readonly ChangelogEntry[] = CHANGELOG): string {
  return entries.reduce((latest, entry) => (entry.date > latest ? entry.date : latest), "");
}
