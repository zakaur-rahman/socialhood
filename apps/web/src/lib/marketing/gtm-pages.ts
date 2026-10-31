/**
 * The go-to-market pages' content (GR-37): Switch from Manychat, the comparisons (Manychat and
 * Interakt in GR-37; LinkDM, InstantDM, Inrō, CreatorFlow, Wati, AiSensy and Spur in C-156) and
 * three feature pages, as data the pages render. The /compare hub lists the comparisons by group
 * (COMPARE_GROUPS). Rules for everything written here:
 *
 * - Our side is checked against the code and docs/CONFLICTS.md (the entry is named next to the
 *   claim). A feature that waits on something the owner has to do is worded that way: "soon" for
 *   Facebook, broadcasts (O-11, the consent check) and the Shopify sync (O-10), "approval"
 *   for Instagram features Meta only delivers after App Review (C-077).
 * - A competitor claim comes from the vendor's own pages first (pricing, help centre, product
 *   updates), read on the date given. A third-party source stays only where the vendor's pages
 *   don't cover the claim, and its comment says so. A comment next to each claim names its source
 *   and date. Never write that a competitor lacks something unless a source says so; "not found"
 *   means the sources we read did not show it. Where an official page contradicts a claim, the
 *   claim follows the official page.
 * - No competitor logos or trademarks beyond the plain names, no "best" or "#1". Each page about a
 *   competitor names it in `competitor`, which shows the trademark and no-affiliation note
 *   (competitor-note.ts) with the latest `checked` date of its sources.
 * - Money: no price of ours is written anywhere; ours comes from Dodo through the plan list.
 */

import table from "./plan-table.json";

export type Status = "yes" | "soon" | "approval" | "no" | "not-found";

export const STATUS_LABEL: Record<Status, string> = {
  yes: "Yes",
  soon: "Coming soon",
  approval: "With Meta's approval",
  no: "Not offered",
  "not-found": "Not found",
};

export type Cell = { status: Status; text?: string };
export type CompareRow = { feature: string; ours: Cell; theirs: Cell };
export type Item = { title: string; body: string };
export type Block = { id: string; title: string; intro?: string; items: Item[] };
export type Source = { label: string; url: string; checked: string };
export type PageLink = { label: string; href: string };

/** A feature page's limits row: Free, Pro and Max as words, read from plan-table.json (C-163). */
export type LimitRow = { label: string; free: string; pro: string; max: string };
/** What an AI action costs, from plan-table.json `credit_costs` (billing/plans.py CREDIT_COSTS). */
export type CreditRow = { label: string; credits: number; per?: string };
/** Something the feature doesn't do yet, with its honest status. */
export type NotYet = { title: string; body: string; status: Status };
export type PageFaq = { question: string; answer: string };
/** A product scene on a feature page (components/marketing/feature-scenes.tsx). */
export type FeatureScene = "inbox" | "comments" | "composer" | "calendar";

/**
 * A feature page's deeper sections (C-163), in the order the page shows them: what it does with a
 * scene, how it works step by step, plans and credits, what it doesn't do yet, who it's for and the
 * page's own questions (plain text: the FAQPage JSON-LD repeats them word for word).
 */
export type FeatureDepth = {
  whatItDoes: { paragraphs: string[]; scene: FeatureScene };
  /** The head's side scene, on a page with no screenshot. */
  headScene?: FeatureScene;
  steps: Item[];
  limits: LimitRow[];
  credits: CreditRow[];
  notYet: NotYet[];
  audience: { creators: string; businesses: string };
  faq: PageFaq[];
};

export type GtmPage = {
  path: string;
  /** The competitor the page is about, for the trademark and no-affiliation note. */
  competitor?: string;
  /** Short name for links and the footer. */
  name: string;
  title: string;
  description: string;
  eyebrow: string;
  h1: string;
  intro: string;
  blocks: Block[];
  compare?: { competitor: string; caption: string; rows: CompareRow[] };
  /** Said plainly under the table or the blocks: what is not done yet and what may change. */
  honesty: string[];
  sources: Source[];
  related: PageLink[];
  /** A feature page's deeper sections (C-163). */
  feature?: FeatureDepth;
  /** The screenshot, if the page shows one (components/marketing/shots). */
  shot?: "inbox" | "aiDraft" | "automationPreview" | "knowledge";
};

// ---- Switch from Manychat

export const SWITCH_PAGE: GtmPage = {
  path: "/switch-from-manychat",
  competitor: "Manychat",
  name: "Switch from Manychat",
  title: "Switch from Manychat",
  description:
    "Moving from Manychat to Amplychat: what you can rebuild, what is different, and what Amplychat adds: an AI inbox, comment analysis and publishing.",
  eyebrow: "Switch from Manychat",
  h1: "Move your Instagram automations from Manychat",
  // "Plans cap features, not contacts" is set against Manychat's billing by active contacts:
  // Manychat help centre "Active Contacts", read 2026-10-29.
  intro:
    "Rebuild your comment and DM automations in an inbox that also answers from your own knowledge, reads every comment and publishes your posts. Plans cap features, not contacts, so a post that goes viral doesn't change your bill.",
  blocks: [
    {
      id: "carries-over",
      title: "What you can rebuild here",
      intro: "You set these up again in Amplychat. There is no one-click import from Manychat.",
      items: [
        {
          title: "Comment-to-DM automations",
          body: "Pick a post, all posts or the next post, match a keyword in three ways or any comment, add random public replies, and send the private reply with a tap-first button or a link.",
        },
        {
          title: "DM keywords and story replies",
          body: "Keyword automations on DMs work as before. A reply to your story starts a story reply automation, and a story mention can start one too.",
        },
        {
          title: "Flows with questions and branches",
          body: "After the trigger, a flow can send messages with quick replies, ask for an email or phone and save it, branch on tags, fields or whether they follow you, wait, split traffic and hand off to a person. It is a step-by-step editor that works on a phone, not a free-form canvas.",
        },
        {
          title: "Contacts, tags and fields",
          body: "Every person gets a contact with tags, custom fields, consent records and a lead stage. Admins export contacts as CSV. There is no contact import yet: people join as they message or comment.",
        },
        {
          title: "Ways in beyond comments",
          body: "Entry links and QR codes, click-to-DM ads, Live comments and ice breakers are built. Meta only sends some of these events to apps it has approved for them, so they reach your account once Meta's approval for Amplychat is complete.",
        },
        {
          title: "Team inbox",
          body: "Invite teammates, assign conversations, use saved replies and set business hours with away messages.",
        },
        {
          title: "Connect your other tools",
          body: "Outbound webhooks on every plan. A public API, API keys, a Zapier app and Google Sheets sync on Pro and Max.",
        },
      ],
    },
    {
      id: "adds",
      title: "What Amplychat adds",
      items: [
        {
          title: "AI that answers from your knowledge",
          body: "Off, Suggest or Auto for each account, with escalation to a person for refunds, complaints, legal threats and anything it can't answer from your knowledge. Questions it couldn't answer are listed so you can fill the gaps.",
        },
        {
          title: "Comment analysis for every post",
          body: "Sentiment, topics, buying signals and spam per post, with a needs-reply count.",
        },
        {
          title: "Publishing in the same app",
          body: "Schedule Instagram images, carousels, Reels and Stories from the calendar, with AI captions and a media library.",
        },
        {
          title: "Flat plans",
          body: "Plan limits are on accounts, automations, AI credits and sends, never on how many contacts you have.",
        },
      ],
    },
    {
      id: "differences",
      title: "What is different, so you can decide",
      items: [
        {
          title: "No free-form canvas",
          body: "Flows are built as steps on a vertical list, with indented branches. Easier on a phone, less free-form.",
        },
        {
          title: "Instagram and WhatsApp first",
          body: "Facebook Pages and Messenger are built but wait on Meta's approval. Amplychat has no TikTok, Telegram, SMS or email channels.",
        },
        {
          // Meta's rule against requiring a follow: Kanal (third-party; Manychat's pages don't state it), read 2026-10-22
          title: "Triggers we don't have",
          body: "Share to DM and follow-based triggers aren't offered. Our follow nudge invites someone to follow but never holds content back until they do, because Meta's rules forbid requiring a follow.",
        },
        {
          title: "WhatsApp broadcasts are coming soon",
          body: "Broadcasts are built and open after our review of consent rules. Until then, Amplychat doesn't send marketing broadcasts.",
        },
      ],
    },
  ],
  honesty: [
    "Instagram and WhatsApp connections depend on Meta's approval of Amplychat's app. Features marked as needing Meta's approval work in our test setup and reach your account once Meta enables them.",
    // help.manychat.com and manychat.com answer automated reads with 403, so on 2026-10-29 their
    // articles were read through a search engine's copy of them (C-155).
    "What we say about Manychat comes from Manychat's own help centre, checked on 29 October 2026. Check manychat.com before you decide.",
  ],
  sources: [
    {
      label: "Manychat help: Active Contacts",
      url: "https://help.manychat.com/hc/en-us/articles/25800323349020-Active-Contacts",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Share to DM trigger",
      url: "https://help.manychat.com/hc/en-us/articles/23431135317916-Share-to-DM-trigger",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Follow to DM on Instagram (beta)",
      url: "https://help.manychat.com/hc/en-us/articles/23096654243740-Follow-to-DM-on-Instagram-Say-Hi-to-New-Followers-BETA",
      checked: "2026-10-29",
    },
    // Third-party: Meta's rule against requiring a follow isn't on Manychat's pages; Kanal summarises it.
    { label: "Kanal: Manychat for Instagram (Meta's rules on follows)", url: "https://getkanal.com/blog/manychat-instagram", checked: "2026-10-22" },
  ],
  related: [
    { label: "Amplychat vs Manychat", href: "/compare/manychat" },
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  shot: "automationPreview",
};

// ---- Amplychat vs Manychat

export const COMPARE_MANYCHAT: GtmPage = {
  path: "/compare/manychat",
  competitor: "Manychat",
  name: "Amplychat vs Manychat",
  title: "Amplychat vs Manychat",
  description:
    "Amplychat and Manychat side by side for Instagram and WhatsApp: automations, AI, comments, publishing, channels and pricing, with dated sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs Manychat",
  intro:
    "Manychat is a mature builder for DM automation with many channels and integrations. Amplychat is an AI inbox for Instagram and WhatsApp that adds comment analysis and publishing. Here is where each is stronger, with sources.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: Manychat help centre (Flow Builder, Share to DM, Follow to DM beta, Free plan channels, SMS, TikTok), read 2026-10-29
          title: "Manychat may fit better if",
          body: "you need a free-form flow canvas, share-to-DM or follow triggers, or channels such as TikTok, Telegram, SMS and email.",
        },
        {
          title: "Amplychat may fit better if",
          body: "you want one inbox that answers from your own knowledge with a person in the loop, comment analysis per post, publishing and a plan that doesn't count contacts.",
        },
      ],
    },
  ],
  compare: {
    competitor: "Manychat",
    caption: "Amplychat and Manychat feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: { status: "yes", text: "Instagram and WhatsApp. Facebook Pages and Messenger are built and wait on Meta's approval." },
        // source: Manychat help centre, read 2026-10-29: Free plan (Instagram, TikTok, Messenger, Telegram), Pro plan (adds WhatsApp, SMS and email), SMS channel (through Twilio), TikTok connection (not for UK or EU accounts). Replaces "TikTok in open beta" (Kanal, 2026-10-22).
        theirs: { status: "yes", text: "Instagram, WhatsApp, Messenger, Telegram, SMS and email, and TikTok outside the UK and EU." },
      },
      {
        feature: "Comment to DM",
        ours: { status: "yes", text: "One post, all posts or the next post; keyword or any comment; public reply variations." },
        // source: Manychat help centre "Instagram Post and Reel Comments trigger", read 2026-10-29. It doesn't confirm every option we had listed, so "The same set" is softened.
        theirs: { status: "yes", text: "Comment triggers on posts and Reels, with keyword matching." },
      },
      {
        feature: "Story replies and mentions",
        ours: { status: "yes" },
        // source: Manychat help centre "Instagram Story Reply Trigger" and "Instagram Story Mention Reply trigger", read 2026-10-29
        theirs: { status: "yes" },
      },
      {
        feature: "Live comments, ads, entry links and QR codes",
        ours: { status: "approval", text: "Built. Meta only sends these events to apps it has approved." },
        // source: Manychat help centre "Instagram Live Comments Trigger", "Instagram Ads Trigger" and "Instagram Ref URL Trigger", read 2026-10-29. QR codes for Instagram aren't named there, so the cell names the three triggers.
        theirs: { status: "yes", text: "Live comment, ad and ref link triggers." },
      },
      {
        feature: "Share to DM and follow to DM",
        ours: { status: "no", text: "Our follow nudge never holds content back until someone follows." },
        // source: Manychat help centre "Share to DM trigger" and "Follow to DM on Instagram [BETA]" (availability decided by Meta), read 2026-10-29
        theirs: { status: "yes", text: "Share to DM; follow to DM is in beta where Meta makes it available." },
      },
      {
        feature: "Flow builder",
        ours: { status: "yes", text: "A step editor with quick replies, questions, branches, delays and a split." },
        // source: Manychat help centre "How to build a Manychat automation" (Flow Builder, a visual editor on a canvas), read 2026-10-29
        theirs: { status: "yes", text: "A visual editor on a canvas." },
      },
      {
        feature: "Contacts, tags and fields",
        ours: { status: "yes", text: "With consent records, a lead stage and CSV export." },
        // source: Manychat help centre "Contacts tab: Overview" (filters, segments, tags) and "Data Collection block and Custom User Fields", read 2026-10-29
        theirs: { status: "yes", text: "Contacts, tags, custom fields and segments." },
      },
      {
        feature: "Broadcasts",
        ours: { status: "soon", text: "WhatsApp broadcasts are built and open after our review of consent rules." },
        // source: Manychat help centre "Broadcasting in Manychat" and "Broadcasting in WhatsApp" (a template reaches everyone; a regular message only people inside the 24-hour window), read 2026-10-29
        theirs: { status: "yes", text: "Broadcasts to your contacts. Outside the 24-hour window, WhatsApp needs an approved template." },
      },
      {
        feature: "Team inbox",
        ours: { status: "yes", text: "Roles, assignment, saved replies and business hours." },
        // source: Manychat help centre "Manychat Inbox", "User roles and team management" and "Conversations auto-assignment", read 2026-10-29
        theirs: { status: "yes", text: "Shared inbox, roles, and manual or automatic assignment, with inbox seats by plan." },
      },
      {
        feature: "Integrations",
        ours: { status: "yes", text: "Webhooks on every plan. API, Zapier app and Google Sheets on Pro and Max." },
        // source: Manychat help centre "Zapier Integration" and "Google Sheets integration", read 2026-10-29. Make is dropped: no Manychat page we read names it.
        theirs: { status: "yes", text: "Zapier, Google Sheets and others." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: { status: "yes", text: "Off, Suggest or Auto, with escalation rules and a list of questions it couldn't answer." },
        // source: Manychat product updates "Your new AI hub (beta)" (2025-10-22) and "Knowledge v2" (2026-02-24), read 2026-10-29: AI replies from links and text you add and routes uncertain messages to your team; help centre "Pro plan" lists AI. Replaces the reviews' "paid add-on" wording (Mooon AI, 2026-10-22).
        theirs: { status: "yes", text: "Manychat AI, in beta, replies from links and text you add and can pass uncertain messages to your team." },
      },
      {
        feature: "Comment analysis per post",
        ours: { status: "yes", text: "Sentiment, topics, buying signals, spam and a summary." },
        // source: Manychat help centre "Instagram Post and Reel Comments trigger", read 2026-10-29: comments start automations; analysis of comments not found
        theirs: { status: "not-found", text: "Comments are used as triggers." },
      },
      {
        feature: "Publishing posts",
        ours: { status: "yes", text: "Instagram images, carousels, Reels and Stories. Facebook publishing waits on Meta's approval." },
        // source: Manychat help centre and product updates, read 2026-10-29: no publishing or post scheduling found
        theirs: { status: "not-found" },
      },
      {
        feature: "How it is priced",
        ours: { status: "yes", text: "Flat plans. Limits are on features, never on contacts." },
        // source: Manychat help centre "Pro plan" and "Active Contacts", read 2026-10-29: plans from 2 March 2026 billed by active contacts a month; Pro $39 a month on monthly billing for 2,500 active contacts; prices can vary by region. Replaces the third-party guides (Chatarmin, Layer3 Labs, DMChamp, 2026-10-22).
        theirs: { status: "yes", text: "By active contacts a month, on plans introduced on 2 March 2026. Pro is $39 a month for 2,500 active contacts on monthly billing." },
      },
    ],
  },
  honesty: [
    // help.manychat.com and manychat.com answer automated reads with 403, so on 2026-10-29 the help
    // articles and pricing were read through a search engine's copy of them (C-155).
    "Manychat's column comes from Manychat's own help centre and product updates, checked on 29 October 2026. \"Not found\" means we didn't see it there, not that Manychat lacks it.",
    "Manychat's plans and prices change and can vary by region, so check manychat.com before you decide.",
    "Our column is checked against our own code. Anything that depends on Meta, Shopify or a legal review says so.",
  ],
  sources: [
    {
      label: "Manychat help: Pro plan",
      url: "https://help.manychat.com/hc/en-us/articles/25800228332572-Pro-plan",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Active Contacts",
      url: "https://help.manychat.com/hc/en-us/articles/25800323349020-Active-Contacts",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Free plan (channels)",
      url: "https://help.manychat.com/hc/en-us/articles/25800197498652-Free-plan",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: How to connect TikTok",
      url: "https://help.manychat.com/hc/en-us/articles/17928990909084-How-to-connect-TikTok-to-Manychat",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Instagram Post and Reel Comments trigger",
      url: "https://help.manychat.com/hc/en-us/articles/14281316989724-Instagram-Post-and-Reel-Comments-trigger",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Instagram Live Comments Trigger",
      url: "https://help.manychat.com/hc/en-us/articles/14281275933724-Instagram-Live-Comments-Trigger",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Instagram Ads Trigger",
      url: "https://help.manychat.com/hc/en-us/articles/14281321942428-Instagram-Ads-Trigger",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Instagram Ref URL Trigger",
      url: "https://help.manychat.com/hc/en-us/articles/14281276006684-Instagram-Ref-URL-Trigger",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Share to DM trigger",
      url: "https://help.manychat.com/hc/en-us/articles/23431135317916-Share-to-DM-trigger",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Follow to DM on Instagram (beta)",
      url: "https://help.manychat.com/hc/en-us/articles/23096654243740-Follow-to-DM-on-Instagram-Say-Hi-to-New-Followers-BETA",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: How to build a Manychat automation",
      url: "https://help.manychat.com/hc/en-us/articles/14281166306332-How-to-build-a-Manychat-automation",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Contacts tab",
      url: "https://help.manychat.com/hc/en-us/articles/14281110746012-Contacts-tab-Overview",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Broadcasting in WhatsApp",
      url: "https://help.manychat.com/hc/en-us/articles/14281461353756-Broadcasting-in-WhatsApp",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Manychat Inbox",
      url: "https://help.manychat.com/hc/en-us/articles/14281070478748-Manychat-Inbox",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: User roles and team management",
      url: "https://help.manychat.com/hc/en-us/articles/14281172274460-User-roles-and-team-management",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Zapier Integration",
      url: "https://help.manychat.com/hc/en-us/articles/14281281340188-Zapier-Integration",
      checked: "2026-10-29",
    },
    {
      label: "Manychat help: Google Sheets integration",
      url: "https://help.manychat.com/hc/en-us/articles/14281248811292-Google-Sheets-integration",
      checked: "2026-10-29",
    },
    {
      label: "Manychat product updates: Your new AI hub (beta)",
      url: "https://community.manychat.com/product-updates/your-new-ai-hub-beta-is-live-smarter-replies-faster-setup-same-manychat-magic-7631",
      checked: "2026-10-29",
    },
    {
      label: "Manychat product updates: Knowledge v2",
      url: "https://community.manychat.com/product-updates/knowledge-v2-import-website-content-and-review-what-your-ai-knows-9132",
      checked: "2026-10-29",
    },
  ],
  related: [
    { label: "Switch from Manychat", href: "/switch-from-manychat" },
    { label: "Amplychat vs Interakt", href: "/compare/interakt" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Amplychat vs Interakt

export const COMPARE_INTERAKT: GtmPage = {
  path: "/compare/interakt",
  competitor: "Interakt",
  name: "Amplychat vs Interakt",
  title: "Amplychat vs Interakt",
  description:
    "Amplychat and Interakt side by side for businesses on WhatsApp and Instagram: campaigns, catalogue, AI, comments and publishing, with sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs Interakt",
  intro:
    "Interakt is built around WhatsApp: bulk campaigns, catalogues and checkout. Amplychat is built around the conversation and the comment: an AI inbox, comment analysis and Instagram publishing. Here is the detail.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          title: "Interakt may fit better if",
          body: "most of your business is WhatsApp campaigns to a list, with a catalogue and checkout inside WhatsApp.",
        },
        {
          title: "Amplychat may fit better if",
          body: "your customers find you through Instagram posts and comments, and you want comments read and answered, replies drafted from your own knowledge and your posts scheduled in the same place.",
        },
      ],
    },
  ],
  compare: {
    competitor: "Interakt",
    caption: "Amplychat and Interakt feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: { status: "yes", text: "WhatsApp and Instagram. Facebook waits on Meta's approval." },
        // source: interakt.shop/pricing, read 2026-10-29: Starter is Instagram only (999 rupees) or one channel; Growth, Advanced and Enterprise list WhatsApp and Instagram
        theirs: { status: "yes", text: "WhatsApp and Instagram, depending on the plan." },
      },
      {
        feature: "Bulk WhatsApp campaigns",
        ours: { status: "soon", text: "Broadcasts are built and open after our review of consent rules. Pro and Max only." },
        // source: interakt.shop/pricing, read 2026-10-29: one-time and ongoing campaigns from Starter; click and conversion tracking from Growth
        theirs: { status: "yes", text: "One-time and ongoing campaigns, with click and conversion tracking from the Growth plan." },
      },
      {
        feature: "Product catalogue",
        ours: {
          status: "approval",
          text: "Add products by hand or CSV; the AI answers price and stock from it, and you can send a product or product list in WhatsApp from the inbox. The WhatsApp catalogue messages need your Meta catalogue set up and Meta's approval. Shopify sync is coming soon. Pro and Max.",
        },
        // source: interakt.shop/pricing, read 2026-10-29: WhatsApp catalogue creation, product and catalogue message templates and Shopify catalogue auto-sync, from Growth
        theirs: { status: "yes", text: "Catalogue creation, product message templates and Shopify catalogue sync, from the Growth plan." },
      },
      {
        feature: "Payments and checkout in chat",
        ours: {
          status: "yes",
          text: "Send a payment request in the chat: a Razorpay link paid to your own Razorpay account, or your UPI ID marked paid by hand. Orders are tracked in the Orders page. Pro and Max. We do not hold your money, and we do not offer WhatsApp Pay.",
        },
        // source: interakt.shop/pricing, read 2026-10-29: "Send Payment Links from Inbox" on Starter; "WhatsApp Checkout Bot" and "Native WhatsApp Payment (WhatsApp Pay)" on Growth. Replaces the third-party guides (Hyperleap, InstantDM, 2026-10-22).
        theirs: { status: "yes", text: "Payment links from the inbox, and a WhatsApp checkout bot with WhatsApp Pay from the Growth plan." },
      },
      {
        feature: "Comment to DM on Instagram",
        ours: { status: "yes", text: "Keyword or any comment, on chosen posts or all, with a private reply." },
        // source: interakt.shop/pricing, read 2026-10-29: Instagram plans list "Unlimited DMs & Comments", "Price Please Automation", giveaway automation and custom auto replies
        theirs: { status: "yes", text: "Comment and DM automations such as price-please replies and giveaways." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: { status: "yes", text: "Off, Suggest or Auto, with escalation rules and a list of unanswered questions." },
        // source: interakt.shop/pricing, read 2026-10-29: "WhatsApp AI Agents" (sales, lead qualification, customer support) as an add-on for Growth and Advanced; AnswerBot runs with up to 5 website URLs. Replaces "early, through a partner" from third-party guides (2026-10-22).
        theirs: { status: "yes", text: "WhatsApp AI agents for sales, lead qualification and support, as a paid add-on on the Growth and Advanced plans." },
      },
      {
        feature: "Comment analysis per post",
        ours: { status: "yes", text: "Sentiment, topics, buying signals, spam and a summary." },
        // source: interakt.shop/pricing, read 2026-10-29: the analytics listed are conversation and agent performance analytics; comment analysis not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Publishing Instagram posts",
        ours: { status: "yes", text: "Images, carousels, Reels and Stories." },
        // source: interakt.shop/pricing, read 2026-10-29: scheduling or publishing posts not found in the plan features
        theirs: { status: "not-found" },
      },
      {
        feature: "Team inbox",
        ours: { status: "yes", text: "Roles, assignment, saved replies and business hours. Seats by plan." },
        // source: interakt.shop/pricing, read 2026-10-29: "Unlimited agents (All Roles)" on the Growth card but "Unlimited Agents (owner role)" in its feature list; all roles on Advanced and Enterprise
        theirs: { status: "yes", text: "Unlimited agents from the Growth plan; the pricing page is unclear which roles Growth includes." },
      },
      {
        feature: "Starting price",
        ours: { status: "yes", text: "A Free plan with no card. See the pricing page for Pro." },
        // source: interakt.shop/pricing, read 2026-10-29: Starter 999 rupees (Instagram only), Growth 2,799, Advanced 3,799, plus taxes. Meta's WhatsApp fees are separate (docs/competitors.md).
        theirs: { status: "yes", text: "₹999 a month for Instagram only and ₹2,799 for WhatsApp and Instagram (Growth), plus taxes." },
      },
    ],
  },
  honesty: [
    "Interakt's column comes from its own pricing page, read on 29 October 2026. Its plans and prices change, so check interakt.shop before you decide.",
    "\"Not found\" means we didn't see it on Interakt's pricing page, not that Interakt lacks it.",
    "Neither company's plans include Meta's WhatsApp messaging fees, which Meta charges to your business.",
  ],
  sources: [{ label: "Interakt pricing", url: "https://www.interakt.shop/pricing/", checked: "2026-10-29" }],
  related: [
    { label: "Amplychat vs Manychat", href: "/compare/manychat" },
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Our side, shared by the C-156 comparisons. Checked against the code: website chat on every
// plan (C-111), Facebook with Meta's approval (C-077), broadcasts after the consent review (O-11),
// knowledge sources faq/text/url/file plus site crawl (migrations 0009, 0030) and products, Meta's
// WhatsApp fees paid by the business to Meta with no markup (owner, 2026-10-29, C-156).

const OURS_CHANNELS: Cell = {
  status: "yes",
  text: "Instagram, WhatsApp and a website chat widget in one inbox. Facebook Pages and Messenger are built and wait on Meta's approval.",
};
const OURS_AI: Cell = {
  status: "yes",
  text: "Answers only from your documents, Q&A, products and website pages. Off, Suggest or Auto, with hand-off to a person and a list of questions it couldn't answer.",
};
const OURS_COMMENT_TO_DM: Cell = { status: "yes", text: "One post, all posts or the next post; keyword or any comment; public reply variations." };
const OURS_COMMENT_ANALYSIS: Cell = { status: "yes", text: "Sentiment, topics, buying signals, spam and a summary for each post." };
const OURS_PUBLISHING: Cell = {
  status: "yes",
  text: "Instagram images, carousels, Reels and Stories from a calendar. Facebook publishing waits on Meta's approval.",
};
const OURS_BROADCASTS: Cell = { status: "soon", text: "WhatsApp broadcasts are built and open after our review of consent rules. Pro and Max." };
const OURS_TEAM: Cell = { status: "yes", text: "Roles, assignment, saved replies and business hours. Seats by plan." };
const OURS_PRICE: Cell = { status: "yes", text: "A Free plan with no card. Plans cap features, never contacts. See the pricing page for Pro." };
const OURS_META_FEES: Cell = {
  status: "yes",
  text: "You pay Meta directly through your own WhatsApp Business account. Amplychat adds no markup.",
};
const OURS_CATALOGUE: Cell = {
  status: "approval",
  text: "Products by hand or CSV, which the AI answers from; product messages in WhatsApp need your Meta catalogue and Meta's approval. Shopify sync is coming soon. Pro and Max.",
};
const OURS_LEAD_CAPTURE: Cell = { status: "yes", text: "A flow asks for an email or phone and saves it to the contact. Contacts export as CSV." };
const OURS_INTEGRATIONS: Cell = { status: "yes", text: "Webhooks on every plan. API, Zapier app and Google Sheets on Pro and Max." };

const OURS_HONESTY = "Our column is checked against our own code. Anything that depends on Meta, Shopify or a legal review says so.";

// ---- Amplychat vs LinkDM (C-156)

export const COMPARE_LINKDM: GtmPage = {
  path: "/compare/linkdm",
  competitor: "LinkDM",
  name: "Amplychat vs LinkDM",
  title: "Amplychat vs LinkDM",
  description:
    "Amplychat and LinkDM side by side for Instagram creators and brands: comment-to-DM, lead capture, AI, WhatsApp, comments and pricing, with dated sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs LinkDM",
  intro:
    "LinkDM is a focused comment-to-DM tool for Instagram and Facebook with a low-cost start. Amplychat puts Instagram, WhatsApp and website chat in one inbox, with AI that answers from your own knowledge, comment analysis and publishing.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: linkdm.com/pricing, read 2026-10-29: Free up to 1,000 DMs a month; Share to Inbox trigger on every plan; Pro $19 a month
          title: "LinkDM may fit better if",
          body: "you mainly send links from comments and Stories, want a free start or a low-cost paid plan for that alone, or use share-to-DM triggers.",
        },
        {
          title: "Amplychat may fit better if",
          body: "customers also reach you on WhatsApp or your website, you want replies drafted from your own knowledge with a person in the loop, or you want comment analysis and publishing in the same app.",
        },
      ],
    },
  ],
  compare: {
    competitor: "LinkDM",
    caption: "Amplychat and LinkDM feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: OURS_CHANNELS,
        // source: linkdm.com FAQ ("only works with Instagram and Facebook") and linkdm.com/pricing ("Facebook Auto-Reply"), read 2026-10-29
        theirs: { status: "yes", text: "Instagram and Facebook. Its FAQ says it works only with those two." },
      },
      {
        feature: "Comment to DM",
        ours: OURS_COMMENT_TO_DM,
        // source: linkdm.com/pricing, read 2026-10-29: "Post & Reels Automation" and "Next Post Feature" on Free; "Comment Auto-Reply", "Advertising Auto-Reply" and "IG Live Auto-Reply" on Pro and Platinum+
        theirs: { status: "yes", text: "Post, Reel and next-post automations on Free; comment, ad and Live auto-replies on Pro." },
      },
      {
        feature: "Story replies and mentions",
        ours: { status: "yes" },
        // source: linkdm.com/pricing, read 2026-10-29: "Story Auto-Reply" and "Story Mention Auto-Reply" on every plan
        theirs: { status: "yes", text: "On every plan." },
      },
      {
        feature: "Share to DM",
        ours: { status: "no" },
        // source: linkdm.com/pricing, read 2026-10-29: "Share to Inbox Trigger" on every plan
        theirs: { status: "yes", text: "A share-to-inbox trigger on every plan." },
      },
      {
        feature: "Lead capture",
        ours: OURS_LEAD_CAPTURE,
        // source: linkdm.com home ("Capture email addresses directly in chat", "Connect lead forms to Kit and Flodesk") and linkdm.com/pricing ("Lead Generation" on Pro), read 2026-10-29
        theirs: { status: "yes", text: "Email capture in chat on Pro, with lead forms sent to Kit and Flodesk." },
      },
      {
        feature: "Broadcasts",
        ours: OURS_BROADCASTS,
        // source: linkdm.com home banner, read 2026-10-29: "Broadcasts let you send timely DMs to active contacts!"
        theirs: { status: "yes", text: "Instagram DMs to active contacts." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: OURS_AI,
        // source: linkdm.com home and linkdm.com/pricing, read 2026-10-29: AI replies not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Team inbox",
        ours: OURS_TEAM,
        // source: linkdm.com/pricing, read 2026-10-29: "Inbox Automation" and "Inbox Conversation Starters" listed; a shared team inbox not found
        theirs: { status: "not-found", text: "Inbox automations are listed; a shared team inbox wasn't." },
      },
      {
        feature: "Comment analysis per post",
        ours: OURS_COMMENT_ANALYSIS,
        // source: linkdm.com home, read 2026-10-29: "Track link click analytics on DMs sent"; comment analysis not found
        theirs: { status: "not-found", text: "Link click analytics on DMs sent." },
      },
      {
        feature: "Publishing posts",
        ours: OURS_PUBLISHING,
        // source: linkdm.com home, read 2026-10-29: "DM Planner" drafts DMs for scheduled posts; scheduling or publishing posts not found
        theirs: { status: "not-found", text: "A DM planner drafts DMs for posts you schedule elsewhere." },
      },
      {
        feature: "How it is priced",
        ours: OURS_PRICE,
        // source: linkdm.com/pricing, read 2026-10-29: Free $0 (1,000 DMs a month, 1 account); Pro $19 USD per month (25,000 DMs, up to 3 accounts) or $182 USD yearly; Platinum+ $99 USD per month or $832 yearly
        theirs: {
          status: "yes",
          text: "By DMs sent. Free for up to 1,000 DMs a month; Pro is $19 a month or $182 a year (25,000 DMs, up to 3 accounts); Platinum+ is $99 a month.",
        },
      },
    ],
  },
  honesty: [
    "LinkDM's column comes from LinkDM's own home and pricing pages, read on 29 October 2026. \"Not found\" means we didn't see it there, not that LinkDM lacks it.",
    "LinkDM's plans and prices change, so check linkdm.com before you decide.",
    OURS_HONESTY,
  ],
  sources: [
    { label: "LinkDM pricing", url: "https://linkdm.com/pricing", checked: "2026-10-29" },
    { label: "LinkDM home page (features and FAQ)", url: "https://linkdm.com/", checked: "2026-10-29" },
  ],
  related: [
    { label: "All comparisons", href: "/compare" },
    { label: "Amplychat vs Manychat", href: "/compare/manychat" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Amplychat vs InstantDM (C-156)

export const COMPARE_INSTANTDM: GtmPage = {
  path: "/compare/instantdm",
  competitor: "InstantDM",
  name: "Amplychat vs InstantDM",
  title: "Amplychat vs InstantDM",
  description:
    "Amplychat and InstantDM side by side for Instagram: comment-to-DM, follow-ups, AI, scheduling, WhatsApp and pricing, with dated sources from both sides.",
  eyebrow: "Compare",
  h1: "Amplychat vs InstantDM",
  intro:
    "InstantDM is an Instagram DM automation tool with low flat prices, follow-up sequences and post scheduling. Amplychat adds WhatsApp and website chat to the same inbox, AI that answers from your own knowledge and comment analysis.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: instantdm.com/pricing and home, read 2026-10-29: follow-before-link gate, DM sequences, Live comment triggers, post scheduling with AutoDM, Legend Pro $9.99 a month billed yearly
          title: "InstantDM may fit better if",
          body: "you work on Instagram alone and want a low price, a follow gate before the link, timed follow-up sequences or Live comment triggers.",
        },
        {
          title: "Amplychat may fit better if",
          body: "your customers also write on WhatsApp or your website, and you want one team inbox where the AI answers from your own knowledge and hands the rest to a person.",
        },
      ],
    },
  ],
  compare: {
    competitor: "InstantDM",
    caption: "Amplychat and InstantDM feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: OURS_CHANNELS,
        // source: instantdm.com/pricing, read 2026-10-29: Facebook Page automation from Legend Pro, Messenger flows from Trendsetter; WhatsApp only as "WhatsApp support"
        theirs: { status: "yes", text: "Instagram, with Facebook Pages and Messenger flows on higher plans. WhatsApp is listed as a support channel, not a messaging channel." },
      },
      {
        feature: "Comment to DM, Stories and Live",
        ours: { status: "yes", text: "Comments and Story replies and mentions. Live comments, ads and entry links are built and wait on Meta's approval." },
        // source: instantdm.com home and pricing, read 2026-10-29: comment-to-DM on posts and Reels, story replies and mentions, "Story, Live and next-post triggers" on Legend Pro
        theirs: { status: "yes", text: "Posts and Reels, Story replies and mentions, and Live comments." },
      },
      {
        feature: "Follow gate",
        ours: { status: "no", text: "Our follow nudge never holds content back until someone follows." },
        // source: instantdm.com home FAQ and pricing ("Follow-before-link gate"), read 2026-10-29
        theirs: { status: "yes", text: "Asks people to follow before it sends the link." },
      },
      {
        feature: "Lead capture and follow-ups",
        ours: { status: "yes", text: "A flow asks for an email or phone, waits and follows up. Contacts export as CSV." },
        // source: instantdm.com/pricing, read 2026-10-29: "Email and phone number collection" on Legend Pro; "DM sequences, up to 10 messages"; delays and follow-ups up to 24 hours in the Flow Editor
        theirs: { status: "yes", text: "Email and phone capture, and DM sequences of up to 10 messages with delays." },
      },
      {
        feature: "AI replies",
        ours: OURS_AI,
        // source: instantdm.com/pricing, read 2026-10-29: "AI comment replies" on Free; "AI agent node with your own OpenAI, Claude, Gemini or DeepSeek key" and "Human takeover" from Trendsetter. A knowledge base isn't mentioned.
        theirs: {
          status: "yes",
          text: "AI comment replies on Free. From Trendsetter, an AI agent step that runs on your own OpenAI, Claude, Gemini or DeepSeek key, with human takeover.",
        },
      },
      {
        feature: "Inbox and contacts",
        ours: OURS_TEAM,
        // source: instantdm.com/pricing, read 2026-10-29: "Inbox with live chat", contacts with tags and CSV export; "Team collaboration tools" on Multi Pro only
        theirs: { status: "yes", text: "An inbox with live chat, contacts, tags and CSV export. Team tools are on the Multi Pro plan." },
      },
      {
        feature: "Publishing posts",
        ours: OURS_PUBLISHING,
        // source: instantdm.com/pricing and home FAQ, read 2026-10-29: "Post scheduling with AutoDM" on Legend Pro; posts, Reels and carousels on the Multi plans
        theirs: { status: "yes", text: "Schedule posts and Reels with the auto-DM attached." },
      },
      {
        feature: "Comment analysis per post",
        ours: OURS_COMMENT_ANALYSIS,
        // source: instantdm.com home, read 2026-10-29: comments are matched by keyword; an account analytics report and dashboards; comment analysis not found
        theirs: { status: "not-found", text: "An analytics report for your account." },
      },
      {
        feature: "Integrations",
        ours: OURS_INTEGRATIONS,
        // source: instantdm.com/pricing, read 2026-10-29: Mailchimp, Kit and Klaviyo, webhooks, API and MCP from Trendsetter
        theirs: { status: "yes", text: "Mailchimp, Kit and Klaviyo, webhooks, an API and MCP from Trendsetter." },
      },
      {
        feature: "How it is priced",
        ours: OURS_PRICE,
        // source: instantdm.com/pricing, read 2026-10-29: Free $0 (500 DM automations a month); Legend Pro $9.99, Trendsetter $24.99, Trendsetter Pro $49.99 per month billed yearly; USD shown by default
        theirs: {
          status: "yes",
          text: "Free for 500 DM automations a month. Legend Pro $9.99, Trendsetter $24.99 and Trendsetter Pro $49.99 a month, billed yearly.",
        },
      },
    ],
  },
  honesty: [
    "InstantDM's column comes from InstantDM's own home and pricing pages, read on 29 October 2026. \"Not found\" means we didn't see it there, not that InstantDM lacks it.",
    "InstantDM's plans and prices change, and its pricing page also offers rupee prices, so check instantdm.com before you decide.",
    OURS_HONESTY,
  ],
  sources: [
    { label: "InstantDM pricing", url: "https://instantdm.com/pricing", checked: "2026-10-29" },
    { label: "InstantDM home page (features and FAQ)", url: "https://instantdm.com/", checked: "2026-10-29" },
  ],
  related: [
    { label: "All comparisons", href: "/compare" },
    { label: "Amplychat vs LinkDM", href: "/compare/linkdm" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Amplychat vs Inrō (C-156)

export const COMPARE_INRO: GtmPage = {
  path: "/compare/inro",
  competitor: "Inrō",
  name: "Amplychat vs Inrō",
  title: "Amplychat vs Inrō",
  description:
    "Amplychat and Inrō side by side for Instagram: AI agents, comment-to-DM, DM campaigns, CRM, WhatsApp, comment analysis and pricing, with dated sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs Inrō",
  intro:
    "Inrō is an Instagram-only DM platform with an AI agent, DM campaigns and a CRM. Amplychat brings Instagram, WhatsApp and website chat into one inbox, with AI from your own knowledge, comment analysis and publishing.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: inro.social home and pricing, read 2026-10-29: DM campaigns to a segment, Shopify, Calendly, Stripe and Make, an MCP server, up to 10 team members on Pro
          title: "Inrō may fit better if",
          body: "Instagram is your only channel and you want DM campaigns to segments today, ready-made Shopify, Calendly or Stripe links, or an MCP server.",
        },
        {
          title: "Amplychat may fit better if",
          body: "you also sell on WhatsApp or your website, want comment analysis and publishing next to the inbox, or want a plan that doesn't count contacts.",
        },
      ],
    },
  ],
  compare: {
    competitor: "Inrō",
    caption: "Amplychat and Inrō feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: OURS_CHANNELS,
        // source: inro.social home FAQ, read 2026-10-29: "Inrō is built exclusively for Instagram"
        theirs: { status: "yes", text: "Instagram. Its FAQ says it is built only for Instagram." },
      },
      {
        feature: "Comment to DM and Stories",
        ours: OURS_COMMENT_TO_DM,
        // source: inro.social/pricing, read 2026-10-29: comment-to-DM, Stories mentions and replies, and ad triggers on all plans (Live is marked differently in two places, so it is left out)
        theirs: { status: "yes", text: "Comments, Story mentions and replies, and ads." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: OURS_AI,
        // source: inro.social home, read 2026-10-29: "Train it on your site, your FAQ and your price list"; tone cloned from past conversations; "Keep whole folders off limits"; it "pulls you in when it matters"; pricing: 50 AI credits on Free
        theirs: {
          status: "yes",
          text: "An AI agent trained on your site, FAQ and price list, in a tone taken from your past chats, that pulls you in when it matters.",
        },
      },
      {
        feature: "Broadcasts and DM campaigns",
        ours: OURS_BROADCASTS,
        // source: inro.social/pricing and home, read 2026-10-29: "Message a segment of your contacts"; 3 campaigns a month on Free, unlimited on Pro and Managed
        theirs: { status: "yes", text: "Instagram DM campaigns to a segment: 3 a month on Free, unlimited on Pro." },
      },
      {
        feature: "Inbox and contacts",
        ours: { status: "yes", text: "A team inbox with roles and assignment; contacts with tags, fields, consent records and CSV export." },
        // source: inro.social home and pricing, read 2026-10-29: "See DMs, comments and contacts in one place"; unlimited CRM contacts; team members 1 on Free, up to 10 on Pro
        theirs: { status: "yes", text: "DMs, comments and unlimited contacts in one place. One team member on Free, up to 10 on Pro." },
      },
      {
        feature: "Integrations",
        ours: OURS_INTEGRATIONS,
        // source: inro.social home ("Shopify, Calendly, Stripe and Make.com out of the box", MCP) and pricing (none on Free; webhooks and API on Pro), read 2026-10-29
        theirs: { status: "yes", text: "Shopify, Calendly, Stripe and Make, with webhooks, an API and MCP on Pro." },
      },
      {
        feature: "Comment analysis per post",
        ours: OURS_COMMENT_ANALYSIS,
        // source: inro.social home and pricing, read 2026-10-29: comments trigger automations and appear in the inbox; comment analysis not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Publishing posts",
        ours: OURS_PUBLISHING,
        // source: inro.social/pricing, read 2026-10-29: "Instagram content management" on Pro and Managed; scheduling or publishing posts not described
        theirs: { status: "not-found", text: "Pro lists Instagram content management; scheduling posts isn't described." },
      },
      {
        feature: "How it is priced",
        ours: OURS_PRICE,
        // source: inro.social/pricing, read 2026-10-29: Free €0 (100 activated contacts a month); Pro "Starting at €12.99 per month", billed monthly, auto-scaling by activated contacts; Annual Pro €1,249 fixed price; Managed from €299 a month
        theirs: {
          status: "yes",
          text: "By activated contacts. Free for 100 a month; Pro from €12.99 a month, rising with contacts; an annual plan at €1,249.",
        },
      },
    ],
  },
  honesty: [
    "Inrō's column comes from Inrō's own home and pricing pages, read on 29 October 2026. \"Not found\" means we didn't see it there, not that Inrō lacks it.",
    "Inrō's plans and prices change, so check inro.social before you decide.",
    OURS_HONESTY,
  ],
  sources: [
    { label: "Inrō pricing", url: "https://www.inro.social/pricing", checked: "2026-10-29" },
    { label: "Inrō home page (features and FAQ)", url: "https://www.inro.social/", checked: "2026-10-29" },
  ],
  related: [
    { label: "All comparisons", href: "/compare" },
    { label: "Amplychat vs CreatorFlow", href: "/compare/creatorflow" },
    { label: "The AI inbox", href: "/features/ai-inbox" },
  ],
};

// ---- Amplychat vs CreatorFlow (C-156)

export const COMPARE_CREATORFLOW: GtmPage = {
  path: "/compare/creatorflow",
  competitor: "CreatorFlow",
  name: "Amplychat vs CreatorFlow",
  title: "Amplychat vs CreatorFlow",
  description:
    "Amplychat and CreatorFlow side by side for Instagram creators: comment-to-DM, follow and email gates, AI, inbox, WhatsApp and pricing, with dated sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs CreatorFlow",
  intro:
    "CreatorFlow is a simple comment-to-DM tool for Instagram creators, with flat prices by DMs sent. Amplychat is an inbox for Instagram, WhatsApp and website chat, with AI that answers from your own knowledge, comment analysis and publishing.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: creatorflow.so home and pricing, read 2026-10-29: you write every message; follow gate and email gate on Pro and Growth; Free 500 DMs a month
          title: "CreatorFlow may fit better if",
          body: "you want to send links from comments and Stories with messages you write yourself, gate a link behind a follow or an email, and keep it simple.",
        },
        {
          title: "Amplychat may fit better if",
          body: "you also answer questions in DMs, on WhatsApp or on your website, and want AI drafts from your own knowledge, a team inbox, comment analysis and publishing.",
        },
      ],
    },
  ],
  compare: {
    competitor: "CreatorFlow",
    caption: "Amplychat and CreatorFlow feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: OURS_CHANNELS,
        // source: creatorflow.so/pricing and home, read 2026-10-29: "Instagram DM and Comment Automation"; no other channel listed
        theirs: { status: "yes", text: "Instagram." },
      },
      {
        feature: "Comment to DM and Story replies",
        ours: OURS_COMMENT_TO_DM,
        // source: creatorflow.so/pricing, read 2026-10-29: comment-to-DM and story reply automation on all plans; "Unlimited keyword triggers" on Free
        theirs: { status: "yes", text: "Comment-to-DM and Story replies on every plan, with unlimited keyword triggers." },
      },
      {
        feature: "Follow gate and email gate",
        ours: { status: "yes", text: "A flow asks for an email before the link. Our follow nudge never holds content back until someone follows." },
        // source: creatorflow.so home and pricing, read 2026-10-29: "Require a follow before the link goes out"; "can require an email before delivering your link"; both on Pro and Growth
        theirs: { status: "yes", text: "A follow gate and an email gate on Pro and Growth." },
      },
      {
        feature: "AI replies",
        ours: OURS_AI,
        // source: creatorflow.so home, read 2026-10-29: "You write every message in your own voice and can add reply variations"; AI replies not found
        theirs: { status: "not-found", text: "Its home page says you write every message, with reply variations." },
      },
      {
        feature: "Inbox and contacts",
        ours: OURS_TEAM,
        // source: creatorflow.so home and pricing, read 2026-10-29: emails saved in a "Contact CRM", CSV export on Pro and Growth, "5 team seats per workspace" on Growth; a DM inbox not found
        theirs: { status: "not-found", text: "Collected emails go to a contact list with CSV export; a DM inbox wasn't described. Growth has 5 team seats." },
      },
      {
        feature: "Analytics",
        ours: { status: "yes", text: "A weekly report, and a lead score on every conversation." },
        // source: creatorflow.so home and pricing, read 2026-10-29: link clicks, leads and conversions, clicks by country ("Geo analytics" on Pro)
        theirs: { status: "yes", text: "Link clicks, leads and conversions, with clicks by country." },
      },
      {
        feature: "Comment analysis per post",
        ours: OURS_COMMENT_ANALYSIS,
        // source: creatorflow.so home, read 2026-10-29: comment analysis not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Publishing posts",
        ours: OURS_PUBLISHING,
        // source: creatorflow.so home and pricing, read 2026-10-29: post scheduling not found
        theirs: { status: "not-found" },
      },
      {
        feature: "How it is priced",
        ours: OURS_PRICE,
        // source: creatorflow.so/pricing, read 2026-10-29: Free $0 (500 DMs a month); Pro $15/mo monthly or $12/mo billed annually ($144/year), 5,000 DMs; Growth $30/mo monthly or $24/mo billed annually ($288/year), 10,000 DMs; "$" with no currency code
        theirs: {
          status: "yes",
          text: "By DMs sent. Free for 500 DMs a month; Pro $15 a month (5,000 DMs) and Growth $30 a month (10,000 DMs), less when billed yearly.",
        },
      },
    ],
  },
  honesty: [
    "CreatorFlow's column comes from CreatorFlow's own home and pricing pages, read on 29 October 2026. \"Not found\" means we didn't see it there, not that CreatorFlow lacks it.",
    "CreatorFlow's pricing page shows prices in dollars without naming the currency, and its plans change, so check creatorflow.so before you decide.",
    OURS_HONESTY,
  ],
  sources: [
    { label: "CreatorFlow pricing", url: "https://creatorflow.so/pricing", checked: "2026-10-29" },
    { label: "CreatorFlow home page (features and FAQ)", url: "https://creatorflow.so/", checked: "2026-10-29" },
  ],
  related: [
    { label: "All comparisons", href: "/compare" },
    { label: "Amplychat vs Inrō", href: "/compare/inro" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Amplychat vs Wati (C-156)

export const COMPARE_WATI: GtmPage = {
  path: "/compare/wati",
  competitor: "Wati",
  name: "Amplychat vs Wati",
  title: "Amplychat vs Wati",
  description:
    "Amplychat and Wati side by side for WhatsApp and Instagram: broadcasts, AI agents, catalogue, comments, publishing, Meta's fees and pricing, with sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs Wati",
  intro:
    "Wati is a broad WhatsApp platform with broadcasts, AI agents and many channels and integrations. Amplychat is built around Instagram comments and DMs as much as WhatsApp, with AI from your own knowledge, comment analysis and publishing.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: wati.io/pricing, read 2026-10-29: unlimited broadcasts on Pro; TikTok and calling in the inbox; HubSpot on Pro, Salesforce on Business
          title: "Wati may fit better if",
          body: "you send large WhatsApp broadcasts today, want TikTok or calling in the same inbox, or need CRM integrations such as HubSpot or Salesforce.",
        },
        {
          title: "Amplychat may fit better if",
          body: "your customers find you through Instagram posts and comments, and you want comments read and answered, posts scheduled and a Free plan to start.",
        },
      ],
    },
  ],
  compare: {
    competitor: "Wati",
    caption: "Amplychat and Wati feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: OURS_CHANNELS,
        // source: wati.io/pricing, read 2026-10-29: Growth's omnichannel inbox "WhatsApp, Calling, Facebook, Instagram, TikTok, Webchat, and RCS and more"
        theirs: { status: "yes", text: "WhatsApp, calling, Facebook, Instagram, TikTok and web chat in one inbox." },
      },
      {
        feature: "Broadcasts",
        ours: OURS_BROADCASTS,
        // source: wati.io/pricing, read 2026-10-29: "15k Broadcasts/month" on Growth, "Unlimited Broadcasts" on Pro and Business; template messages charged extra
        theirs: { status: "yes", text: "15,000 a month on Growth, unlimited on Pro and Business. Template messages cost extra." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: OURS_AI,
        // source: wati.io/pricing (1 Astra AI agent on Growth, 2 on Pro, "human hand-off" on Pro) and Astra help "How to train your AI agent" (website links, PDF, Word, text and Markdown files, Q&A pairs), read 2026-10-29
        theirs: {
          status: "yes",
          text: "Astra AI agents trained on website pages, documents and Q&A pairs, with hand-off to a teammate. One agent on Growth, two on Pro.",
        },
      },
      {
        feature: "Instagram comments and DMs",
        ours: OURS_COMMENT_TO_DM,
        // source: wati.io home, read 2026-10-29: Instagram Automation can "Auto-reply to every DM, comment and story reply"
        theirs: { status: "yes", text: "Auto-replies to DMs, comments and Story replies." },
      },
      {
        feature: "Catalogue and commerce",
        ours: OURS_CATALOGUE,
        // source: wati.io/pricing, read 2026-10-29: "Catalog, Shopify abandoned cart, order templates" on Growth; Shopify integration add-on USD 4.99/Month
        theirs: { status: "yes", text: "A catalogue, Shopify abandoned-cart and order messages from Growth. The Shopify integration is a $4.99 a month add-on." },
      },
      {
        feature: "Team inbox",
        ours: OURS_TEAM,
        // source: wati.io/pricing, read 2026-10-29: Growth 3 users, "No additional users"; Pro and Business 5 users, more at a monthly price per user
        theirs: { status: "yes", text: "3 users on Growth with no extra users; 5 on Pro and Business, with more at a monthly price per user." },
      },
      {
        feature: "Integrations",
        ours: OURS_INTEGRATIONS,
        // source: wati.io/pricing, read 2026-10-29: "2 select Commerce/CRM integrations" and no webhooks on Growth; 5 incl. HubSpot and limited webhooks on Pro; unlimited incl. Salesforce on Business
        theirs: { status: "yes", text: "2 integrations on Growth, 5 including HubSpot on Pro, unlimited on Business. Webhooks from Pro." },
      },
      {
        feature: "Comment analysis per post",
        ours: OURS_COMMENT_ANALYSIS,
        // source: wati.io home and pricing, read 2026-10-29: comment analysis or sentiment not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Publishing posts",
        ours: OURS_PUBLISHING,
        // source: wati.io home and pricing, read 2026-10-29: post publishing or scheduling not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Meta's WhatsApp fees",
        ours: OURS_META_FEES,
        // source: wati.io/pricing, read 2026-10-29: "Additional charges apply for template messages", by category and the recipient's country code, with a rate card per plan; a markup isn't stated either way
        theirs: { status: "yes", text: "Charged on top of the plan for template messages, by category and country, from Wati's rate card." },
      },
      {
        feature: "How it is priced",
        ours: OURS_PRICE,
        // source: wati.io/pricing, read 2026-10-29: Growth ₹2,699, Pro ₹5,799, Business ₹16,799 per month, billed quarterly (monthly and annual billing also offered)
        theirs: { status: "yes", text: "Growth ₹2,699, Pro ₹5,799 and Business ₹16,799 a month, billed quarterly." },
      },
    ],
  },
  honesty: [
    "Wati's column comes from Wati's own home page, pricing page and help centre, read on 29 October 2026. \"Not found\" means we didn't see it there, not that Wati lacks it.",
    "Wati's prices change and may differ by region and billing period, so check wati.io before you decide.",
    "Meta's WhatsApp message fees are separate from both companies' plans.",
    OURS_HONESTY,
  ],
  sources: [
    { label: "Wati pricing", url: "https://www.wati.io/pricing/", checked: "2026-10-29" },
    { label: "Wati home page (features)", url: "https://www.wati.io/", checked: "2026-10-29" },
    { label: "Wati help: How to train your AI agent", url: "https://astra-help.wati.io/en/articles/11755911-how-to-train-your-ai-agent", checked: "2026-10-29" },
    {
      label: "Wati help: Set up an Astra AI agent for Instagram",
      url: "https://support.wati.io/en/articles/17634410-how-to-set-up-an-astra-ai-agent-for-instagram",
      checked: "2026-10-29",
    },
  ],
  related: [
    { label: "All comparisons", href: "/compare" },
    { label: "Amplychat vs Interakt", href: "/compare/interakt" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Amplychat vs AiSensy (C-156)

export const COMPARE_AISENSY: GtmPage = {
  path: "/compare/aisensy",
  competitor: "AiSensy",
  name: "Amplychat vs AiSensy",
  title: "Amplychat vs AiSensy",
  description:
    "Amplychat and AiSensy side by side for businesses on WhatsApp: broadcasts, chatbots, AI agents, catalogue, Instagram, Meta's fees and pricing, with sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs AiSensy",
  intro:
    "AiSensy is a WhatsApp marketing platform built for broadcasts, chatbots and selling in WhatsApp. Amplychat puts WhatsApp next to Instagram comments and DMs and website chat, with AI from your own knowledge, comment analysis and publishing.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: aisensy.com/pricing (chatbot builder and AI agent add-ons, catalogue, UPI and card payments) and aisensy.com/aisensy-vs-interakt (5 agents and 1 owner), read 2026-10-29
          title: "AiSensy may fit better if",
          body: "WhatsApp is your main channel and you want broadcasts now, a drag-and-drop chatbot builder, payments by UPI or card inside WhatsApp and five agent logins.",
        },
        {
          title: "Amplychat may fit better if",
          body: "Instagram matters to you as much as WhatsApp, and you want comment-to-DM automations, comment analysis and publishing next to an AI inbox.",
        },
      ],
    },
  ],
  compare: {
    competitor: "AiSensy",
    caption: "Amplychat and AiSensy feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: OURS_CHANNELS,
        // source: aisensy.com/pricing and aisensy.com/aisensy-vs-interakt, read 2026-10-29: WhatsApp; Instagram messaging not found on AiSensy's pages (a site search found only WhatsApp links from Instagram ads and bios)
        theirs: { status: "yes", text: "WhatsApp. Instagram messaging wasn't on the pages we read." },
      },
      {
        feature: "Broadcasts",
        ours: OURS_BROADCASTS,
        // source: aisensy.com/aisensy-vs-interakt, read 2026-10-29: broadcasts ("Time taken for 10,000 Messages Broadcast"); broadcast scheduling on the Pro plan
        theirs: { status: "yes", text: "WhatsApp broadcasts, with scheduling on the Pro plan." },
      },
      {
        feature: "Chatbot flows",
        ours: { status: "yes", text: "A step editor with quick replies, questions, branches, delays and a split." },
        // source: aisensy.com/pricing, read 2026-10-29: "Drag & Drop Chatbot Builder" add-on ₹2,500/month or ₹2,250/month billed annually, 5 chatbots
        theirs: { status: "yes", text: "A drag-and-drop chatbot builder, an add-on at ₹2,500 a month (₹2,250 billed yearly)." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: OURS_AI,
        // source: aisensy.com/pricing, read 2026-10-29: "WhatsApp AI Agent Builder" add-on ₹1,350/month or ₹1,215/month billed annually, with 1,000 AI messages and knowledge base Q&A
        theirs: { status: "yes", text: "A WhatsApp AI agent builder with knowledge base answers, an add-on at ₹1,350 a month with 1,000 AI messages." },
      },
      {
        feature: "Catalogue and payments",
        ours: {
          status: "yes",
          text: "Products the AI answers from, and payment requests by Razorpay link or your UPI ID, on Pro and Max. WhatsApp product messages need Meta's approval.",
        },
        // source: aisensy.com/pricing and aisensy.com/aisensy-vs-interakt, read 2026-10-29: "Sell Products on WhatsApp" (WhatsApp Catalog) and "Collect Payments via UPI & Card"
        theirs: { status: "yes", text: "A WhatsApp catalogue and payments by UPI and card." },
      },
      {
        feature: "Instagram comment to DM",
        ours: OURS_COMMENT_TO_DM,
        // source: aisensy.com pages and a site search, read 2026-10-29: Instagram comment automation not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Team inbox",
        ours: OURS_TEAM,
        // source: aisensy.com/aisensy-vs-interakt, read 2026-10-29: "Agent logins: 5 Agents + 1 Owner"
        theirs: { status: "yes", text: "5 agents and 1 owner." },
      },
      {
        feature: "Comment analysis per post",
        ours: OURS_COMMENT_ANALYSIS,
        // source: aisensy.com/pricing and aisensy.com/aisensy-vs-interakt, read 2026-10-29: comment analysis not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Publishing posts",
        ours: OURS_PUBLISHING,
        // source: aisensy.com/pricing and aisensy.com/aisensy-vs-interakt, read 2026-10-29: publishing posts not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Meta's WhatsApp fees",
        ours: OURS_META_FEES,
        // source: aisensy.com/pricing, read 2026-10-29: WhatsApp Conversation Credits are managed separately and "charged directly by Meta"; "AiSensy doesn't charge a single penny to procure the WhatsApp Business API"
        theirs: { status: "yes", text: "Bought separately as WhatsApp conversation credits. AiSensy says it charges nothing to set up the WhatsApp Business API." },
      },
      {
        feature: "How it is priced",
        ours: OURS_PRICE,
        // source: aisensy.com/aisensy-vs-interakt, read 2026-10-29: "Starts at ₹1500/month", "Pro plan, priced at ₹3,200/month"; aisensy.com/pricing: prepaid, monthly, quarterly (5% off) or yearly (10% off). The plan cards on aisensy.com/pricing didn't load for us, so the plan prices come from AiSensy's own comparison page.
        theirs: { status: "yes", text: "From ₹1,500 a month; Pro is ₹3,200 a month. Prepaid, with discounts for quarterly or yearly billing." },
      },
    ],
  },
  honesty: [
    "AiSensy's column comes from AiSensy's own pricing page and its comparison page with Interakt, read on 29 October 2026. The plan prices are from the comparison page, because the plan cards didn't load for us. \"Not found\" means we didn't see it there, not that AiSensy lacks it.",
    "AiSensy's plans and prices change, so check aisensy.com before you decide.",
    "Meta's WhatsApp message fees are separate from both companies' plans.",
    OURS_HONESTY,
  ],
  sources: [
    { label: "AiSensy pricing", url: "https://www.aisensy.com/pricing", checked: "2026-10-29" },
    { label: "AiSensy vs Interakt (AiSensy's own page)", url: "https://aisensy.com/aisensy-vs-interakt", checked: "2026-10-29" },
  ],
  related: [
    { label: "All comparisons", href: "/compare" },
    { label: "Amplychat vs Wati", href: "/compare/wati" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Amplychat vs Spur (C-156)

export const COMPARE_SPUR: GtmPage = {
  path: "/compare/spur",
  competitor: "Spur",
  name: "Amplychat vs Spur",
  title: "Amplychat vs Spur",
  description:
    "Amplychat and Spur side by side for WhatsApp, Instagram and website chat: AI agents, comment-to-DM, broadcasts, Shopify, comments and pricing, with sources.",
  eyebrow: "Compare",
  h1: "Amplychat vs Spur",
  intro:
    "Spur and Amplychat both put WhatsApp, Instagram and website chat in one inbox with an AI agent. Spur leans into Shopify stores and broadcasts; Amplychat adds comment analysis, publishing and a Free plan.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          // source: spurnow.com/en/llm-info (native Shopify app; Messenger and email channels) and spurnow.com/en/pricing (unlimited broadcasts on every plan), read 2026-10-29
          title: "Spur may fit better if",
          body: "you run a Shopify store and want orders and products synced, broadcasts today, or Messenger and email in the same inbox.",
        },
        {
          title: "Amplychat may fit better if",
          body: "you want to start free, see what people say in your Instagram comments, schedule your posts in the same app and pay Meta's WhatsApp fees to Meta directly.",
        },
      ],
    },
  ],
  compare: {
    competitor: "Spur",
    caption: "Amplychat and Spur feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: OURS_CHANNELS,
        // source: spurnow.com/en/llm-info (last reviewed 2026-10-07), read 2026-10-29: "WhatsApp, Instagram DMs and comments, Facebook Messenger, website live chat and email"; email is a paid add-on
        theirs: { status: "yes", text: "WhatsApp, Instagram, Messenger and website live chat, with email as a paid add-on." },
      },
      {
        feature: "Comment to DM",
        ours: OURS_COMMENT_TO_DM,
        // source: spurnow.com/en/llm-info, read 2026-10-29: a DM, link or product to everyone who comments a keyword on a post, Reel or Live, with an optional public reply
        theirs: { status: "yes", text: "Keyword comments on posts, Reels and Live get a DM, link or product, with an optional public reply." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: OURS_AI,
        // source: spurnow.com/en/llm-info (trained on "product catalog, website and FAQs"; hands the chat to a person) and spurnow.com/en/pricing (1 to 3 AI agents by plan; "AI Agent to Live Chat Escalation"), read 2026-10-29
        theirs: { status: "yes", text: "AI agents trained on your product catalogue, website and FAQs, with hand-off to a person. 1 to 3 agents by plan." },
      },
      {
        feature: "Broadcasts",
        ours: OURS_BROADCASTS,
        // source: spurnow.com/en/pricing (unlimited broadcasts on every plan) and llm-info (segments, scheduling, split across days), read 2026-10-29
        theirs: { status: "yes", text: "Unlimited WhatsApp broadcasts to segments on every plan, scheduled and split across days." },
      },
      {
        feature: "Flows",
        ours: { status: "yes", text: "A step editor with quick replies, questions, branches, delays and a split." },
        // source: spurnow.com/en/pricing, read 2026-10-29: 3 flows on Instagram and Facebook only on AI Acquire ("AI Acquire does not include WhatsApp automation"); 25, 50 or unlimited on WhatsApp, Instagram and Facebook on higher plans
        theirs: { status: "yes", text: "3 flows on Instagram and Facebook on AI Acquire, with no WhatsApp automation; 25 to unlimited on higher plans." },
      },
      {
        feature: "Shopify and catalogue",
        ours: OURS_CATALOGUE,
        // source: spurnow.com/en/llm-info (native Shopify app syncing customers, orders and products; WooCommerce) and spurnow.com/en/pricing (WhatsApp catalog $39 a month), read 2026-10-29
        theirs: { status: "yes", text: "A Shopify app that syncs customers, orders and products, and WooCommerce. A WhatsApp catalogue is a $39 a month add-on." },
      },
      {
        feature: "Team inbox",
        ours: OURS_TEAM,
        // source: spurnow.com/en/pricing, read 2026-10-29: 1, 2, 5 and 10 users on AI Acquire, AI Start, AI Accelerate and AI Max
        theirs: { status: "yes", text: "1 to 10 users by plan." },
      },
      {
        feature: "Comment analysis per post",
        ours: OURS_COMMENT_ANALYSIS,
        // source: spurnow.com home and llm-info, read 2026-10-29: comment-triggered DMs; comment analysis not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Publishing posts",
        ours: OURS_PUBLISHING,
        // source: spurnow.com home and llm-info, read 2026-10-29: publishing or scheduling posts not found
        theirs: { status: "not-found" },
      },
      {
        feature: "Meta's WhatsApp fees",
        ours: OURS_META_FEES,
        // source: spurnow.com/en/llm-info and /en/pricing, read 2026-10-29: WhatsApp charges are separate from the plan, billed per delivered message at Spur's published rates (India marketing $0.0189 to $0.0212)
        theirs: { status: "yes", text: "Separate from the plan, billed per delivered message at Spur's published rates." },
      },
      {
        feature: "How it is priced",
        ours: OURS_PRICE,
        // source: spurnow.com/en/pricing ("$12 per month, $144 billed annually" for AI Acquire; AI Max "$399" a month, "$4,790 billed annually") and llm-info (AI Acquire 15 USD a month; no free plan; 14-day trial on every plan), read 2026-10-29
        theirs: {
          status: "yes",
          text: "AI Acquire is $15 a month, or $12 a month billed yearly; AI Max is $399 a month billed yearly. Each plan has a 14-day trial, and Spur's own page says there is no free plan.",
        },
      },
    ],
  },
  honesty: [
    "Spur's column comes from Spur's own home page, pricing page and its page for AI assistants, read on 29 October 2026. \"Not found\" means we didn't see it there, not that Spur lacks it.",
    "Spur publishes prices in several currencies and they change, so check spurnow.com before you decide.",
    OURS_HONESTY,
  ],
  sources: [
    { label: "Spur pricing", url: "https://www.spurnow.com/en/pricing", checked: "2026-10-29" },
    { label: "Spur: information for AI assistants", url: "https://www.spurnow.com/en/llm-info", checked: "2026-10-29" },
    { label: "Spur home page (features and FAQ)", url: "https://www.spurnow.com/", checked: "2026-10-29" },
  ],
  related: [
    { label: "All comparisons", href: "/compare" },
    { label: "Amplychat vs Wati", href: "/compare/wati" },
    { label: "The AI inbox", href: "/features/ai-inbox" },
  ],
};

// ---- Feature pages
//
// C-163: each feature page goes deeper (`feature`): what it does with a product scene, how it works
// step by step, the limits on each plan (read from plan-table.json, never typed) and the AI credits
// (plan-table.json `credit_costs`, exported from billing/plans.py CREDIT_COSTS and kept equal by
// apps/api/tests/unit/test_marketing_plan_table.py), what it doesn't do yet, who it's for and the
// page's own questions (none of them on /faq, so the page may mark them up as FAQPage). Every claim
// names its source in the comment above it. Meta's rules are quoted from Meta's own developer docs,
// read 2026-10-31 (the `sources` of the page).

const E = table.entitlements;
const CREDITS = table.credit_costs;
const count = new Intl.NumberFormat("en-US");
type PlanKey = keyof typeof E;
type Plans<T> = Record<"free" | "pro" | "max", T>;

/** A plan's number as the pricing page words it: null is "No limit" (billing/plans.py). */
const amount = (value: number | null, unit = "") => (value === null ? "No limit" : `${count.format(value)}${unit}`);

/** One row of a feature page's limits table, read from plan-table.json; `word` says a plan's value. */
function planRow(label: string, key: PlanKey, word: (value: unknown) => string = (value) => amount(value as number | null)): LimitRow {
  const values = E[key] as Plans<unknown>;
  return { label, free: word(values.free), pro: word(values.pro), max: word(values.max) };
}

const days = (value: unknown) => (value === null ? "No limit" : `${count.format(value as number)} days`);
const modes = (value: unknown) => ((value as string[]).includes("auto") ? "Off, Suggest, Auto" : "Off, Suggest");
/** Words for a credit count. */
const credits = (n: number) => `${n} ${n === 1 ? "credit" : "credits"}`;

// services/comments/analysis.py COMMENTS_PER_CREDIT: comment_analysis is charged per 20 comments,
// rounded up for each batch (ai/metering.py).
const COMMENTS_PER_CREDIT = 20;

/** The Meta developer docs the feature pages quote (read 2026-10-31 with an automated read). */
const META_IG_MESSAGING: Source = {
  label: "Meta for Developers: Instagram Messaging API",
  url: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api",
  checked: "2026-10-31",
};
const META_WA_WINDOW: Source = {
  label: "Meta for Developers: WhatsApp Cloud API, sending messages",
  url: "https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages",
  checked: "2026-10-31",
};
const META_IG_PRIVATE_REPLIES: Source = {
  label: "Meta for Developers: Instagram private replies",
  url: "https://developers.facebook.com/docs/instagram-platform/private-replies",
  checked: "2026-10-31",
};

export const FEATURE_COMMENT_INTELLIGENCE: GtmPage = {
  path: "/features/comment-intelligence",
  name: "Comment intelligence",
  title: "Comment intelligence for Instagram",
  description:
    "See what people say on each Instagram post: sentiment, topics, buying signals and spam, with a summary per post. Reply, DM, hide or delete from one page.",
  eyebrow: "Comment intelligence",
  h1: "Know what your comments are telling you",
  intro:
    "Every comment is read for sentiment, questions, buying signals and spam. Each post gets a summary and topics, so you can find the comments that need a reply without scrolling.",
  blocks: [
    {
      id: "inside",
      title: "What you get",
      items: [
        // schemas/posts.py CommentAnalysis: sentiment, intent (models/ai.py Intent), is_spam, a topic of at most 3 words.
        { title: "Reads every comment", body: "Each comment gets a sentiment, an intent such as a price question, a purchase or a complaint, a short topic and a spam flag." },
        // services/comments/summaries.py: two or three sentences, at most 6 labels with their count and sentiment.
        { title: "Summarises each post", body: "Two or three sentences and up to six topics, each with how many comments it covers and how people feel about it." },
        // schemas/posts.py CommentFilter: the post detail's filter chips.
        { title: "Filters that find the work", body: "Positive, neutral, negative, questions, buying signals, spam, hidden and needs reply, each a tap away." },
        // schemas/posts.py PostSort: recent or needs_reply.
        { title: "Sorts posts by what needs you", body: "Sort the posts grid by the newest or by the comments still waiting for a reply, so the busiest conversations come first." },
        // services/comments/actions.py: public reply, private reply, hide, unhide, delete (admins).
        { title: "Acts from one page", body: "Reply in public, send one private DM, hide or unhide a comment. Admins can also delete." },
        // models/connections.py auto_hide_spam (off by default); AccountCard "Hide spam comments".
        { title: "You stay in charge", body: "Spam is hidden only on accounts where you turn on Hide spam comments. Nothing is deleted without you." },
      ],
    },
  ],
  feature: {
    whatItDoes: {
      paragraphs: [
        "Say a Reel takes off overnight. Some comments ask the price, some ask where to buy, a few are spam links, and most say they love it. Reading them all in the Instagram app takes an evening.",
        // services/comments/summaries.py and schemas/posts.py CommentFilter (needs_reply).
        "In Amplychat the post shows a short summary, its main topics with how people feel about each, and filters for questions, buying signals, spam and comments that still need a reply. Open Needs reply, answer in public or by DM, hide the spam, and move on.",
      ],
      scene: "comments",
    },
    steps: [
      // services/comments/backfill.py: the 25 most recent posts, up to 200 comments each; the 6-hourly sync.
      {
        title: "Connect Instagram",
        body: "Amplychat stores your 25 most recent posts and brings in their comments, up to 200 a post. New comments arrive as they are posted, and a sync every 6 hours fills any gaps.",
      },
      // services/comments/analysis.py: every 30 seconds, batches of up to 50, oldest first; schemas/posts.py CommentStats.
      {
        title: "Comments are read in batches",
        body: "Every 30 seconds new comments are read in batches of up to 50, oldest first. A busy post is worked through in order, and it shows how many comments are read so far.",
      },
      // services/comments/analysis.py step 4 (FR-CMT-05): spam hidden before the batch is stored, when auto-hide is on.
      {
        title: "Spam is hidden, if you chose that",
        body: "On an account with Hide spam comments on, a comment marked as spam is hidden on Instagram straight away. If Instagram refuses, the comment stays visible.",
      },
      // services/comments/summaries.py: after 20 new analysed comments, when 24 hours behind, or on Refresh.
      {
        title: "Each post gets its summary",
        body: "The summary refreshes after every 20 newly read comments, at least once a day while new comments come in, or when you press Refresh.",
      },
      // schemas/posts.py CommentFilter needs_reply: not replied, not spam, not hidden, last 7 days.
      {
        title: "You answer what matters",
        body: "Needs reply lists comments from the last 7 days that you haven't answered and that aren't spam or hidden. Reply in public or send a private DM from the same row.",
      },
    ],
    limits: [
      planRow("Posts with comment intelligence, per account", "comment_intelligence_posts", (value) =>
        value === null ? "Every post" : `Latest ${count.format(value as number)}`,
      ),
      planRow("AI credits a month", "ai_credits_monthly"),
      planRow("Accounts per platform", "accounts_per_platform"),
      planRow("Team members", "members"),
    ],
    credits: [
      { label: "Reading comments", credits: CREDITS.comment_analysis, per: `for every ${COMMENTS_PER_CREDIT} comments or part of them` },
      { label: "A post summary", credits: CREDITS.post_summary },
    ],
    notYet: [
      // landing/Channels.tsx Facebook Pages, C-077: built, waits on Meta's approval.
      { title: "Facebook Page comments", status: "approval", body: "Page comments are built and join the same page once Meta approves Amplychat for them." },
      // landing/Channels.tsx "Live comments and ads": Meta only sends these events to approved apps.
      { title: "Comments during a Live", status: "approval", body: "Comments made during an Instagram Live reach Amplychat once Meta approves those events." },
      // landing/Channels.tsx: post insights need a permission production doesn't ask for yet (C-155).
      { title: "Reach and saves for each post", status: "approval", body: "Post insights follow Meta's approval. Comment counts and likes work today." },
      // platforms/: instagram, facebook, whatsapp and web only.
      { title: "Other networks", status: "no", body: "Amplychat doesn't read comments on TikTok, YouTube or other networks." },
    ],
    audience: {
      // comment_intelligence_posts (plan-table.json).
      creators: `See what your audience asks under each Reel, which topics land and which posts still have questions waiting, so your next post answers them. Free covers your ${E.comment_intelligence_posts.free} latest posts for each account.`,
      businesses: "Spot buying signals and price questions on product posts and answer them before the customer moves on. Hide spam automatically, so a launch post stays clean.",
    },
    faq: [
      // services/comments/backfill.py (25 posts, 200 comments); analysis.py comment_intelligence_posts.
      {
        question: "Does Amplychat read comments on my older posts?",
        answer: `When you connect, it brings in your 25 most recent posts and up to 200 comments on each, and new comments arrive as they are posted. On Free, analysis covers the ${E.comment_intelligence_posts.free} most recent posts of each account; on Pro and Max it covers every post.`,
      },
      // services/comments/actions.py hide and unhide; analysis.py auto-hide; delete is for admins.
      {
        question: "Does hiding spam delete the comment?",
        answer:
          "No. A hidden comment stays on Instagram, out of view on your post, and you can unhide it. Auto-hide only hides comments the AI marks as spam, on accounts where you turned it on. Deleting is a separate action for admins.",
      },
      // Meta, Instagram private replies (read 2026-10-31): one message, within 7 days of the comment.
      // platforms/buckets.py: at most 750 private replies an hour per account, shared with automations.
      {
        question: "How many private replies can I send to one comment?",
        answer:
          "One, within 7 days of the comment. That is Instagram's rule, and Amplychat checks it before sending. Private replies from you and from automations go out at no more than 750 an hour for each account.",
      },
      // analysis.py step 1 (FR-PRV-02): with AI analysis off nothing reaches the provider; comments are skipped.
      // analysis.py step 2 (FR-AI-05): with credits used up, waiting comments are skipped, not queued.
      {
        question: "Can I use the comments page without the AI reading my comments?",
        answer:
          "Yes. Turn AI analysis off for the account and no comment text is sent to the AI. Comments still arrive and you can reply, hide and delete them, but they aren't tagged, summarised or hidden as spam. The same happens to new comments while your AI credits are used up.",
      },
    ],
  },
  honesty: ["Comment analysis needs your Instagram account connected, which depends on Meta's approval of Amplychat's app."],
  sources: [META_IG_PRIVATE_REPLIES],
  related: [
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: "The comment-to-DM guide", href: "/guides/comment-to-dm-automations" },
    { label: "Publishing", href: "/features/publishing" },
    { label: "Amplychat vs Manychat", href: "/compare/manychat" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  shot: "inbox",
};

export const FEATURE_AI_INBOX: GtmPage = {
  path: "/features/ai-inbox",
  name: "The AI inbox",
  title: "AI inbox that replies from your own knowledge",
  description:
    "One inbox for Instagram DMs and WhatsApp chats. AI drafts or sends replies from your knowledge, and hands over the rest.",
  eyebrow: "The AI inbox",
  h1: "One inbox that answers from what you know",
  intro:
    "Instagram DMs and WhatsApp chats arrive in real time with intent, sentiment and a lead score. The AI replies from your own knowledge base, and when it isn't sure it hands the conversation to a person.",
  blocks: [
    {
      id: "inside",
      title: "What's in the inbox",
      items: [
        // explainers/content.ts (the inbox stage): story replies and mentions (C-082, C-083); website chat (GR-28).
        { title: "One list for every channel", body: "Instagram DMs, story replies and mentions, WhatsApp chats and your website chat arrive in real time, in one list." },
        // models/ai.py Intent and Sentiment; services/analysis.py: lead score 0 to 100, crossing 70 notifies every member once.
        { title: "Every message read and tagged", body: "Intent, sentiment and a lead score from 0 to 100. When a lead crosses 70, your team is told once." },
        { title: "You choose how much the AI does", body: "Off, Suggest or Auto for each account. Suggest drafts a reply for you to send. Auto replies by itself when it is confident, and is part of Pro." },
        // schemas/inbox.py Suggestion.sources.
        { title: "Only your knowledge", body: "Answers come from the documents, questions and products you add, and each draft shows what it used. When the answer isn't there it doesn't guess." },
        // models/ai.py EscalationReason; services/sending.py human_takeover.
        { title: "Escalation you can rely on", body: "Refunds, legal threats, complaints, abuse, low confidence, or your own phrases go to Needs you. Replying yourself pauses the AI." },
        // services/knowledge/gaps.py: similar questions matched and counted, most asked first; an answer becomes knowledge.
        { title: "Questions it couldn't answer", body: "Similar questions are grouped and counted, most asked first. Answer one and it joins your knowledge." },
        // services/summaries.py (up to three sentences and a next step); services/polish.py (adds nothing new).
        { title: "Summaries and AI polish", body: "A long thread gets a summary with a suggested next step. AI polish tidies your own draft and refuses to add prices, links or numbers you didn't write." },
        // services/assignment.py (round-robin), saved_replies.py ("/" shortcuts), business_hours.py (away message).
        { title: "Assign, save replies, set hours", body: "Assign conversations by hand or in turn, insert saved replies with a slash, and send an away message outside business hours." },
      ],
    },
  ],
  feature: {
    whatItDoes: {
      paragraphs: [
        "Picture a Tuesday morning. Overnight, someone on Instagram asked whether the linen shirt comes in M, a visitor on your website asked about returns, and a WhatsApp customer wants to know if you take bulk orders.",
        // services/suggestions (drafts with sources); ai/policy.py out_of_knowledge; services/sending.py takeover.
        "In Amplychat all three sit in one list, already tagged. The shirt and returns questions have drafts waiting, each showing the knowledge it used. Bulk orders isn't in your knowledge, so the AI doesn't guess: that conversation is at the top under Needs you, and the question is saved as a gap to fill.",
      ],
      scene: "inbox",
    },
    steps: [
      // FAQ_ACCOUNT_LOGIN; platforms/instagram/oauth.py; Embedded Signup; WidgetSettingsPage (one line of code).
      {
        title: "Connect your channels",
        body: "Instagram with Instagram's own login, for Business and Creator accounts. WhatsApp with a number your business owns, through Meta's Embedded Signup. Website chat with one line of code. Amplychat never asks for your password.",
      },
      // models/ai.py KnowledgeType; POST /knowledge/test.
      {
        title: "Add what you know",
        body: "Text, questions and answers, links, files and your website's pages. Test a question to see the answer and the source it came from.",
      },
      // services/analysis.py: deferred 4 s so a burst is read once, with the last 12 messages as context.
      {
        title: "A message arrives and is read",
        body: "A few seconds after the customer stops typing, their newest message is read with the conversation around it and tagged. A burst of messages is read once.",
      },
      // ai/policy.py: the 13 checks in order; MAX_AI_REPLIES_PER_HOUR = 5 per conversation (services/suggestions/auto.py).
      {
        title: "The AI drafts, or replies on Pro",
        body: "In Suggest, the draft waits for you. In Auto, a reply goes out only after 13 checks pass, among them: the reply window is open, nobody asked for a person, it isn't a refund or complaint, the answer is grounded in your knowledge, and the AI has sent fewer than 5 replies in that conversation in the last hour.",
      },
      // FAQ_TAKEOVER (services/sending.py human_takeover, models/ai.py TAKEOVER_MINUTES).
      {
        title: "You step in whenever you like",
        body: "When you reply yourself, in Amplychat or in the Instagram app, the AI pauses on that conversation for 2 hours by default. You can change the pause to 30 minutes, 24 hours or until you resume the AI.",
      },
      // services/knowledge/gaps.py and sources.py (an FAQ created from a gap answers it).
      {
        title: "Gaps become knowledge",
        body: "Questions the AI couldn't answer wait on the Knowledge page with real examples. Add the answer once, and the next customer who asks gets it.",
      },
    ],
    limits: [
      planRow("Accounts per platform", "accounts_per_platform"),
      planRow("Team members", "members"),
      planRow("AI credits a month", "ai_credits_monthly"),
      planRow("AI modes", "ai_modes", modes),
      planRow("Knowledge, in characters", "knowledge_characters"),
      planRow("Website pages read", "crawl_pages"),
      planRow("Message history", "message_history_days", days),
      planRow("Scheduled messages waiting", "pending_scheduled_messages"),
      planRow("New website chats a day", "widget_conversations_daily"),
    ],
    credits: [
      { label: "Reading a message", credits: CREDITS.message_analysis },
      { label: "A draft reply", credits: CREDITS.reply_suggestion },
      { label: "An automatic reply", credits: CREDITS.auto_reply },
      { label: "A conversation summary", credits: CREDITS.conversation_summary },
      { label: "AI polish on your draft", credits: CREDITS.reply_polish },
      { label: "A test question", credits: CREDITS.knowledge_test },
    ],
    notYet: [
      // landing/Channels.tsx Facebook Pages (C-077).
      { title: "Facebook Messenger", status: "approval", body: "Messenger chats are built and join the inbox once Meta approves Amplychat for them." },
      // services/reply_window.py: Human Agent only when IG_HUMAN_AGENT_ENABLED (Meta approves it for the app).
      // Meta, Instagram Messaging API (read 2026-10-31): the 24-hour window and the separate 7-day Human Agent window.
      {
        title: "Replies after 24 hours on Instagram",
        status: "approval",
        body: "Meta lets a person reply for up to 7 days with its Human Agent tag. Amplychat supports it and turns it on once Meta grants it; until then Instagram replies follow the 24-hour window.",
      },
      // settings.broadcasts_enabled = False (O-11, the consent review).
      { title: "WhatsApp broadcasts", status: "soon", body: "Broadcasts are built and open after our review of consent rules." },
      // SWITCH_PAGE "Instagram and WhatsApp first"; platforms/.
      { title: "Other channels", status: "no", body: "Amplychat has no TikTok, Telegram, SMS or email inbox." },
    ],
    audience: {
      // models/ai.py Intent.COLLABORATION.
      creators: "Fans ask the same things about your gear, your rates and your next drop. Let the AI draft those answers from your own notes, while collaboration requests are tagged as their own kind of message for you to answer.",
      businesses: "Price, stock, delivery and order questions arrive on several channels. Your team works one list with assignment, saved replies and business hours, and every lead is scored so ready buyers don't wait.",
    },
    faq: [
      // ai/policy.py: Auto on Pro only; small talk (C-062) may be answered without a source; FACT_INTENTS need one.
      {
        question: "Which messages does the AI answer on its own?",
        answer:
          "Only in Auto mode, which is part of Pro, and only when all 13 checks pass. A greeting or a thank-you can be answered without your knowledge; a question about price, stock or delivery needs a source from it. Everything else waits for you.",
      },
      // components/ai/DecisionInfo.tsx: the info button on an AI-sent message, its checks and "Should not have sent".
      {
        question: "Can I see why the AI sent a reply?",
        answer:
          "Yes. Every message the AI sent has an info button that shows each check it passed. If a reply shouldn't have gone out, mark it as Should not have sent.",
      },
      // services/business_hours.py: auto_mode out_of_hours; the away message once per closed window.
      {
        question: "Can Auto mode reply only outside business hours?",
        answer:
          "Yes. Set business hours for the workspace or for one account, and choose that Auto replies only while you're closed. During open hours the AI's draft waits for your team. An away message can go out once each time you close.",
      },
      // services/analysis.py step 1 (FR-PRV-02); AccountCard "AI analysis".
      {
        question: "Can I turn the AI off for one account?",
        answer:
          "Yes. With AI analysis off for an account, none of its messages are sent to the AI, so nothing is tagged or drafted there. The inbox, assignment and saved replies keep working.",
      },
      // CREDIT_COSTS message_analysis 1, reply_suggestion 2; services/analysis.py (a burst read once).
      {
        question: "How many AI credits does a typical question use?",
        answer: `About ${CREDITS.message_analysis + CREDITS.reply_suggestion}: reading the message uses ${credits(CREDITS.message_analysis)} and a draft or an automatic reply uses ${credits(CREDITS.reply_suggestion)}. Several messages sent together are read once.`,
      },
    ],
  },
  honesty: [
    // Meta, Instagram Messaging API and WhatsApp Cloud API (read 2026-10-31); services/reply_window.py.
    "Instagram only allows a business to message within 24 hours of the customer's last message, and WhatsApp allows only approved templates after 24 hours. Amplychat shows when the window closes. Website chat has no window.",
    "The AI uses credits from your monthly allowance. Plan limits are on the pricing page.",
  ],
  sources: [META_IG_MESSAGING, META_WA_WINDOW],
  related: [
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "The Instagram DM auto-reply guide", href: "/guides/instagram-dm-auto-replies" },
    { label: "How Amplychat works", href: "/how-it-works" },
    { label: "Amplychat vs Interakt", href: "/compare/interakt" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  shot: "aiDraft",
};

export const FEATURE_PUBLISHING: GtmPage = {
  path: "/features/publishing",
  name: "Publishing",
  title: "Schedule Instagram posts and Stories",
  description:
    "Schedule Instagram images, carousels, Reels and Stories from one calendar, with AI captions, a media library and hashtag groups, next to your inbox.",
  eyebrow: "Publishing",
  h1: "Plan your posts where your customers reply",
  intro:
    "Schedule Instagram posts from a calendar, then watch the comments and DMs they bring in the same app. Publishing sits next to the inbox, so you can see what each post produced.",
  blocks: [
    {
      id: "inside",
      title: "What you can do",
      items: [
        // services/scheduled_posts/rules.py (format from the files); models/publishing.py CAROUSEL_MIN/MAX_ASSETS,
        // STORY_LIFETIME; a Story is one image or one video (STORY_ONE_FILE).
        { title: "Images, carousels, Reels and Stories", body: "The format follows your files: one image is a post, one video a Reel, 2 to 10 files a carousel. A Story is one image or one video and disappears after 24 hours." },
        // services/scheduled_posts/calendar.py and slots.py.
        { title: "A calendar and a queue", body: "Week, month and list views. Set weekly posting times for each account, and Add to queue picks the next free one." },
        // services/captions.py: brand voice, up to 20 hashtags (SUGGESTED_HASHTAGS_MAX); caption_generation.
        { title: "AI captions and hashtags", body: `Draft a caption from a short brief in your brand voice, or get up to 20 hashtag ideas, then edit them. Each uses ${credits(CREDITS.caption_generation)}.` },
        // services/scheduled_posts/hashtag_groups.py: 1 to 30 hashtags, inserted with a click.
        { title: "Hashtag groups", body: "Save sets of up to 30 hashtags and add one to a caption or a first comment with a click." },
        // services/scheduled_posts/library.py.
        { title: "A media library", body: "Images and videos you upload for posts stay in the library, newest first, to filter by type and date and reuse." },
        // services/scheduled_posts/best_times.py: MAX_POSTS 90, MIN_POSTS 10, no AI model.
        { title: "Best posting times", body: "A suggested hour for each weekday from your own last 90 posts, once you have 10. Plain arithmetic, so it uses no AI credits." },
        // services/post_publishing/extras.py, COLLABORATORS_MAX 3; first comment (FR-PUB-11).
        { title: "Collaborators, tags and a first comment", body: "Invite up to 3 Instagram collaborators to a post, carousel or Reel, add a location and user tags, and post a first comment once it's live." },
      ],
    },
  ],
  feature: {
    whatItDoes: {
      paragraphs: [
        "Say you plan your week on Sunday evening: a photo for Tuesday, a Reel for Thursday and a Story for Saturday. Upload the files once, write the captions or draft them with AI, and drop each post into a free posting time on the calendar.",
        // services/post_publishing/publish.py: link_scheduled_post and link_next_posts (FR-AUT-18).
        "When a post goes out, its comments and DMs land in the same app. A comment-to-DM automation set for that post, or for your next post, starts working the moment it's live.",
      ],
      scene: "composer",
    },
    headScene: "calendar",
    steps: [
      // services/scheduled_posts/posts.py: targets (accounts), caption_override per target, drafts autosave.
      {
        title: "Compose once",
        body: "Pick one or more accounts, add your files and write the caption, with a different caption for each account if you like. Drafts save as you go.",
      },
      // services/scheduled_posts/rules.py checklist; models/publishing.py CAPTION_MAX_CHARS, MAX_HASHTAGS, MAX_MENTIONS.
      {
        title: "Check before you schedule",
        body: "A checklist looks at the format, a caption of up to 2,200 characters with at most 30 hashtags and 20 mentions, and video lengths. A post with a problem can't be scheduled until it's fixed.",
      },
      // services/scheduled_posts/slots.py (MIN_SCHEDULE_LEAD 5 minutes, the queue within 8 weeks); posts.py counted_at.
      {
        title: "Pick a time or add to the queue",
        body: "Choose a time at least 5 minutes ahead, or let the queue take the next posting time that is free on every account you picked. Each post counts once toward the month's scheduled posts.",
      },
      // services/post_publishing/publish.py: the quota first, polls the video, never publishes a container twice;
      // models/publishing.py PUBLISH_ATTEMPTS = 3.
      {
        title: "Amplychat publishes it",
        body: "It checks the account's Instagram publishing limit first, waits for a video to finish processing, retries short failures up to 3 times, and never publishes the same post twice.",
      },
      // publish.py: post_first_comment, automations linked, owners and admins notified of a failure;
      // collaborators.py: checked every hour for three days.
      {
        title: "After it's live",
        body: "The first comment goes up, collaborator invites are checked every hour for three days, and linked automations start. If a post fails, owners and admins are told why and can edit and retry it.",
      },
    ],
    limits: [
      planRow("Scheduled posts a month", "scheduled_posts_monthly"),
      planRow("Accounts per platform", "accounts_per_platform"),
      planRow("AI credits a month", "ai_credits_monthly"),
      planRow("Team members", "members"),
    ],
    credits: [
      { label: "An AI caption", credits: CREDITS.caption_generation },
      { label: "Hashtag ideas", credits: CREDITS.caption_generation },
      // best_times.py: no AI model involved.
      { label: "Best posting times", credits: 0 },
    ],
    notYet: [
      // C-077; services/scheduled_posts/rules.py (Facebook formats are built).
      { title: "Facebook Pages", status: "approval", body: "Publishing to a Facebook Page is built and waits on Meta's approval." },
      // landing/Channels.tsx (C-155); best_times.py falls back to likes and comments.
      { title: "Reach and saves for each post", status: "approval", body: "Post insights follow Meta's approval. Until then, best posting times use likes and comments." },
      // The existing honesty line: WhatsApp has no publishing API.
      { title: "WhatsApp", status: "no", body: "WhatsApp has no publishing API, so there is nothing to schedule there." },
      // The media editor is parked (feature/media-editor), not in the product.
      { title: "A photo and video editor", status: "no", body: "There is no built-in editor yet. Upload finished files." },
      // platforms/: instagram, facebook, whatsapp and web only.
      { title: "Other networks", status: "no", body: "Amplychat doesn't publish to TikTok, YouTube, LinkedIn or X." },
    ],
    audience: {
      creators: "Keep a steady rhythm of Reels, carousels and Stories, tag collaborators on brand work, and have your comment-to-DM automation ready for the next post before it's live.",
      // accounts_per_platform (plan-table.json).
      businesses: `Plan launches and offers across up to ${E.accounts_per_platform.pro} Instagram accounts on Pro and ${E.accounts_per_platform.max} on Max, keep captions in your brand voice, and see the questions each post brings in the inbox.`,
    },
    faq: [
      // jobs/tasks/publishing.py dispatch_due_posts (server side, every 30 s); posts.py (a failed post can be edited and retried).
      {
        question: "Do I need to keep Amplychat open for a post to go out?",
        answer:
          "No. Posts are published from our servers at the time you set, whether or not you're signed in. If one fails, owners and admins are told why and can edit and retry it.",
      },
      // posts.py targets and caption_override; slots.py (the queue's shared free time).
      {
        question: "Can one post go to several Instagram accounts?",
        answer:
          "Yes. Pick several accounts in the composer, with a different caption for each if you like. Add to queue finds the next posting time that is free on every account you picked.",
      },
      // models/publishing.py STORY_VIDEO_MIN_S 3, STORY_VIDEO_MAX_S 60; rules.py STORY_NO_CAPTION, EXTRAS_NOT_ON_STORIES.
      {
        question: "Can I schedule a Story with a video?",
        answer:
          "Yes. A Story is one image, or one video from 3 to 60 seconds. Stories go out without a caption, collaborators or tags.",
      },
      // services/scheduled_posts/posts.py: edit, move or unschedule while draft or scheduled (409 once publishing);
      // services/post_publishing/collaborators.py: collaborators can't be added or changed after publishing.
      {
        question: "Can I change a post after it's scheduled?",
        answer:
          "Yes, until it starts publishing: edit it, move it to another time or unschedule it. Once a post is live, Amplychat can't add or change its collaborators.",
      },
      // posts.py counted_at: once per post per billing period; scheduled_posts_monthly (plan-table.json).
      {
        question: "What counts toward the monthly scheduled posts?",
        answer: `Each post counts once, when you schedule it or publish it now, however many accounts it goes to. Free schedules ${amount(E.scheduled_posts_monthly.free)} posts a month and Pro ${amount(E.scheduled_posts_monthly.pro)}; Max ${E.scheduled_posts_monthly.max === null ? "has no limit" : `schedules ${amount(E.scheduled_posts_monthly.max)}`}.`,
      },
    ],
  },
  honesty: ["Instagram and WhatsApp connections depend on Meta's approval of Amplychat's app. Publishing works for Instagram today and, once approved, for Facebook Pages."],
  sources: [],
  related: [
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: "The comment-to-DM guide", href: "/guides/comment-to-dm-automations" },
    { label: "Amplychat vs Manychat", href: "/compare/manychat" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

export const GTM_PAGES: GtmPage[] = [
  SWITCH_PAGE,
  COMPARE_MANYCHAT,
  COMPARE_INTERAKT,
  COMPARE_LINKDM,
  COMPARE_INSTANTDM,
  COMPARE_INRO,
  COMPARE_CREATORFLOW,
  COMPARE_WATI,
  COMPARE_AISENSY,
  COMPARE_SPUR,
  FEATURE_COMMENT_INTELLIGENCE,
  FEATURE_AI_INBOX,
  FEATURE_PUBLISHING,
];

export const PRICING_PATH = "/pricing";

/** The comparisons hub (C-156). */
export const COMPARE_PATH = "/compare";

/** The comparisons hub's groups, in the order the hub shows them (C-156). */
export const COMPARE_GROUPS: { id: string; title: string; intro: string; pages: GtmPage[] }[] = [
  {
    id: "instagram-dm-tools",
    title: "Instagram DM tools",
    intro: "Comment-to-DM and DM automation tools, mostly for creators and Instagram-first brands.",
    pages: [COMPARE_MANYCHAT, SWITCH_PAGE, COMPARE_LINKDM, COMPARE_INSTANTDM, COMPARE_INRO, COMPARE_CREATORFLOW],
  },
  {
    id: "whatsapp-platforms",
    title: "WhatsApp platforms",
    intro: "WhatsApp Business platforms for broadcasts, support and selling in chat.",
    pages: [COMPARE_INTERAKT, COMPARE_WATI, COMPARE_AISENSY, COMPARE_SPUR],
  },
];

export const GTM_PATHS = [...GTM_PAGES.map((page) => page.path), COMPARE_PATH, PRICING_PATH];
