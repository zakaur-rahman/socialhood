/**
 * The go-to-market pages' content (GR-37): Switch from Manychat, two comparisons and three feature
 * pages, as data the pages render. Rules for everything written here:
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
    "What we say about Manychat comes from Manychat's own help centre, checked on 29 October 2026. Its help centre blocks automated reading, so we checked it through a search engine's copy. Check manychat.com before you decide.",
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
    "Manychat's column comes from Manychat's own help centre and product updates, checked on 29 October 2026. Its help centre and pricing page block automated reading, so we checked those pages through a search engine's copy. \"Not found\" means we didn't see it there, not that Manychat lacks it.",
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
  FEATURE_COMMENT_INTELLIGENCE,
  FEATURE_AI_INBOX,
  FEATURE_PUBLISHING,
];

export const PRICING_PATH = "/pricing";
export const GTM_PATHS = [...GTM_PAGES.map((page) => page.path), PRICING_PATH];
