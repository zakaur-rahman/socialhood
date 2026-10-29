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
      id: "what-it-does",
      title: "What it does",
      items: [
        { title: "Reads every comment", body: "Each comment is marked as a question, a buying signal or spam, with its sentiment." },
        { title: "Summarises each post", body: "A short summary and the main topics for the post, and how many comments still need a reply." },
        { title: "Sorts posts by what needs you", body: "The posts grid shows which posts have comments waiting, so the busiest conversations come first." },
        { title: "Acts from one page", body: "Reply publicly, send a DM, hide or delete a comment. Hide spam automatically if you choose." },
      ],
    },
    {
      id: "limits",
      title: "How it is limited",
      items: [
        { title: "Free analyses your latest posts", body: "Free reads the comments on your latest posts for each account. Pro reads every post." },
        { title: "It uses AI credits", body: "Analysing a comment costs a credit and summarising a post's comments costs two. The pricing page lists the allowance for each plan." },
        { title: "You stay in charge", body: "Amplychat hides spam only when you turn that on. Nothing is deleted without you." },
      ],
    },
  ],
  honesty: ["Comment analysis needs your Instagram account connected, which depends on Meta's approval of Amplychat's app."],
  sources: [],
  related: [
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: "Publishing", href: "/features/publishing" },
    { label: "Amplychat vs Manychat", href: "/compare/manychat" },
  ],
  shot: "inbox",
};

export const FEATURE_AI_INBOX: GtmPage = {
  path: "/features/ai-inbox",
  name: "The AI inbox",
  title: "The AI inbox for Instagram and WhatsApp",
  description:
    "One inbox for Instagram DMs and WhatsApp chats. AI drafts or sends replies from your knowledge, and hands over the rest.",
  eyebrow: "The AI inbox",
  h1: "One inbox that answers from what you know",
  intro:
    "Instagram DMs and WhatsApp chats arrive in real time with intent, sentiment and a lead score. The AI replies from your own knowledge base, and when it isn't sure it hands the conversation to a person.",
  blocks: [
    {
      id: "how-it-works",
      title: "How it works",
      items: [
        { title: "You choose how much the AI does", body: "Off, Suggest or Auto for each account. Suggest drafts a reply for you to send. Auto replies by itself when it is confident, and is part of Pro." },
        { title: "Only your knowledge", body: "Answers come from the documents, questions and products you add. When the answer isn't there it doesn't guess." },
        { title: "Escalation you can rely on", body: "Refunds, legal threats, complaints, abuse, low confidence, or your own phrases go to Needs you. Replying yourself pauses the AI." },
        { title: "Questions it couldn't answer", body: "Each unanswered question is recorded, so you know what to add to your knowledge." },
      ],
    },
    {
      id: "team",
      title: "Built for a team",
      items: [
        { title: "Assign, save replies, set hours", body: "Assign conversations, reuse saved replies and send an away message outside business hours." },
        { title: "Ask Amplychat", body: "Ask about your own posts, comments and conversations in plain words. Answers cite the figures they used, and anything it prepares waits for your approval." },
      ],
    },
  ],
  honesty: [
    "Instagram only allows a business to message within 24 hours of the customer's last message. Amplychat shows when the window closes.",
    "The AI uses credits from your monthly allowance. Plan limits are on the pricing page.",
  ],
  sources: [],
  related: [
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
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
      id: "what-it-does",
      title: "What you can do",
      items: [
        { title: "Images, carousels, Reels and Stories", body: "Compose once and schedule. A Story is a single photo that disappears after 24 hours." },
        { title: "A calendar and a queue", body: "Week, month and list views, a posting queue and posting times." },
        { title: "AI captions and hashtags", body: "Draft a caption or hashtags, then edit them. Each uses one AI credit." },
        { title: "A media library", body: "Upload once and reuse." },
        { title: "Best posting times", body: "Suggestions from how your own posts performed." },
      ],
    },
    {
      id: "limits",
      title: "Limits and what is coming",
      items: [
        { title: "Scheduled posts a month", body: "The number depends on the plan. See the pricing page." },
        { title: "Facebook Pages are coming soon", body: "Publishing to a Facebook Page is built and waits on Meta's approval." },
      ],
    },
  ],
  honesty: ["WhatsApp has no publishing API, so publishing is for Instagram and, once approved, Facebook Pages."],
  sources: [],
  related: [
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "The AI inbox", href: "/features/ai-inbox" },
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
