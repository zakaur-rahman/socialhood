/**
 * The go-to-market pages' content (GR-37): Switch from Manychat, two comparisons and three feature
 * pages, as data the pages render. Rules for everything written here:
 *
 * - Our side is checked against the code and docs/CONFLICTS.md (the entry is named next to the
 *   claim). A feature that waits on something the owner has to do is worded that way: "soon" for
 *   Facebook, broadcasts (O-11, the India consent check) and the Shopify sync (O-10), "approval"
 *   for Instagram features Meta only delivers after App Review (C-077).
 * - A competitor claim is only what docs/competitors.md or docs/competitor-manychat.md record
 *   with a source, or what was read from the vendor's own page on the date given. A comment next
 *   to each claim names that source and date. Never write that a competitor lacks something unless
 *   a source says so; "not found" means the sources we read did not show it.
 * - No competitor logos or trademarks beyond the plain names, no "best" or "#1".
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
  name: "Switch from Manychat",
  title: "Switch from Manychat",
  description:
    "Moving from Manychat to Social Hood: what you can rebuild (comment and DM automations, flows, tags, fields), what is different, and what Social Hood adds: an AI inbox, comment analysis and publishing on a flat plan.",
  eyebrow: "Switch from Manychat",
  h1: "Move your Instagram automations from Manychat",
  intro:
    "Rebuild your comment and DM automations in an inbox that also answers from your own knowledge, reads every comment and publishes your posts. Plans cap features, not contacts, so a post that goes viral doesn't change your bill.",
  blocks: [
    {
      id: "carries-over",
      title: "What you can rebuild here",
      intro: "You set these up again in Social Hood. There is no one-click import from Manychat.",
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
          body: "Entry links and QR codes, click-to-DM ads, Live comments and ice breakers are built. Meta only sends some of these events to apps it has approved for them, so they reach your account once Meta's approval for Social Hood is complete.",
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
      title: "What Social Hood adds",
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
          body: "Facebook Pages and Messenger are built but wait on Meta's approval. Social Hood has no TikTok, Telegram, SMS or email channels.",
        },
        {
          title: "Triggers we don't have",
          body: "Share to DM and follow-based triggers aren't offered. Our follow nudge invites someone to follow but never holds content back until they do, because Meta's rules forbid requiring a follow.",
        },
        {
          title: "WhatsApp broadcasts are coming soon",
          body: "Broadcasts are built and open after our review of India's consent rules. Until then, Social Hood doesn't send marketing broadcasts.",
        },
      ],
    },
  ],
  honesty: [
    "Instagram and WhatsApp connections depend on Meta's approval of Social Hood's app. Features marked as needing Meta's approval work in our test setup and reach your account once Meta enables them.",
    "Manychat's own pages block automated reading, so what we say about Manychat comes from third-party guides written in 2026 and read on 2026-10-22. Check manychat.com before you decide.",
  ],
  sources: [
    { label: "Kanal: Manychat for Instagram (triggers, Meta rules)", url: "https://getkanal.com/blog/manychat-instagram", checked: "2026-10-22" },
    { label: "Chatarmin: Manychat pricing 2026", url: "https://chatarmin.com/en/blog/manychat-pricing", checked: "2026-10-22" },
  ],
  related: [
    { label: "Social Hood vs Manychat", href: "/compare/manychat" },
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  shot: "automationPreview",
};

// ---- Social Hood vs Manychat

export const COMPARE_MANYCHAT: GtmPage = {
  path: "/compare/manychat",
  name: "Social Hood vs Manychat",
  title: "Social Hood vs Manychat",
  description:
    "A side-by-side of Social Hood and Manychat for Instagram and WhatsApp: automations, AI, comments, publishing, channels and how each is priced, with the sources and the date they were read.",
  eyebrow: "Compare",
  h1: "Social Hood vs Manychat",
  intro:
    "Manychat is a mature builder for DM automation with many channels and integrations. Social Hood is an AI inbox for Instagram and WhatsApp that adds comment analysis and publishing. Here is where each is stronger, with sources.",
  blocks: [
    {
      id: "choose",
      title: "Which fits you",
      items: [
        {
          title: "Manychat may fit better if",
          body: "you need a free-form flow canvas, share-to-DM or follow triggers, or channels such as TikTok, Telegram, SMS and email.",
        },
        {
          title: "Social Hood may fit better if",
          body: "you want one inbox that answers from your own knowledge with a person in the loop, comment analysis per post, publishing and a plan that doesn't count contacts.",
        },
      ],
    },
  ],
  compare: {
    competitor: "Manychat",
    caption: "Social Hood and Manychat feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: { status: "yes", text: "Instagram and WhatsApp. Facebook Pages and Messenger are built and wait on Meta's approval." },
        // source: competitor-manychat.md section 1 (Kanal, Setsmart; read 2026-10-22)
        theirs: { status: "yes", text: "Instagram, WhatsApp, Messenger, Telegram, SMS and email, and TikTok in open beta." },
      },
      {
        feature: "Comment to DM",
        ours: { status: "yes", text: "One post, all posts or the next post; keyword or any comment; public reply variations." },
        // source: competitor-manychat.md section 1, Kanal (2026-10-22)
        theirs: { status: "yes", text: "The same set." },
      },
      {
        feature: "Story replies and mentions",
        ours: { status: "yes" },
        // source: competitor-manychat.md section 1 (Kanal, 2026-10-22)
        theirs: { status: "yes" },
      },
      {
        feature: "Live comments, ads, entry links and QR codes",
        ours: { status: "approval", text: "Built. Meta only sends these events to apps it has approved." },
        // source: competitor-manychat.md section 1 (Kanal, 2026-10-22)
        theirs: { status: "yes" },
      },
      {
        feature: "Share to DM and follow to DM",
        ours: { status: "no", text: "Our follow nudge never holds content back until someone follows." },
        // source: competitor-manychat.md section 1; Manychat community post 2025-11-06 (read 2026-10-22)
        theirs: { status: "yes", text: "Share to DM; follow to DM is in beta." },
      },
      {
        feature: "Flow builder",
        ours: { status: "yes", text: "A step editor with quick replies, questions, branches, delays and a split." },
        // source: competitor-manychat.md section 1 (visual drag-and-drop canvas; Kanal, 2026-10-22)
        theirs: { status: "yes", text: "A visual drag-and-drop canvas." },
      },
      {
        feature: "Contacts, tags and fields",
        ours: { status: "yes", text: "With consent records, a lead stage and CSV export." },
        // source: competitor-manychat.md section 1 (2026-10-22)
        theirs: { status: "yes", text: "Contacts, tags, custom fields and segments." },
      },
      {
        feature: "Broadcasts",
        ours: { status: "soon", text: "WhatsApp broadcasts are built and open after our review of India's consent rules." },
        // source: competitor-manychat.md section 1 (2026-10-22)
        theirs: { status: "yes", text: "To segments: WhatsApp templates, and Instagram within the 24 hour window." },
      },
      {
        feature: "Team inbox",
        ours: { status: "yes", text: "Roles, assignment, saved replies and business hours." },
        // source: competitor-manychat.md section 1; Guideflow tutorials (2026-10-22)
        theirs: { status: "yes", text: "Shared inbox, roles and conversation assignment." },
      },
      {
        feature: "Integrations",
        ours: { status: "yes", text: "Webhooks on every plan. API, Zapier app and Google Sheets on Pro and Max." },
        // source: competitor-manychat.md section 1; Zapier's Manychat page (2026-10-22)
        theirs: { status: "yes", text: "Zapier, Make, Google Sheets and others." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: { status: "yes", text: "Off, Suggest or Auto, with escalation rules and a list of questions it couldn't answer." },
        // source: competitor-manychat.md section 2 item 3 (Mooon AI review, 2026-10-22); sources differ on whether it is an add-on or in Pro
        theirs: { status: "yes", text: "Reviews describe it as a paid add-on that puts generated replies into a scripted flow." },
      },
      {
        feature: "Comment analysis per post",
        ours: { status: "yes", text: "Sentiment, topics, buying signals, spam and a summary." },
        // source: competitor-manychat.md section 2 item 2: comments are triggers; analysis not found (2026-10-22)
        theirs: { status: "not-found", text: "Comments are used as triggers." },
      },
      {
        feature: "Publishing posts",
        ours: { status: "yes", text: "Instagram images, carousels, Reels and Stories. Facebook publishing waits on Meta's approval." },
        // source: competitor-manychat.md section 2 item 1: no publishing found (2026-10-22)
        theirs: { status: "not-found" },
      },
      {
        feature: "How it is priced",
        ours: { status: "yes", text: "Flat plans. Limits are on features, never on contacts." },
        // source: Chatarmin, Layer3 Labs, DMChamp 2026 (read 2026-10-22): billed by active contacts since 2 March 2026; Pro from $39 a month for 2,500 contacts. Indicative; check manychat.com.
        theirs: { status: "yes", text: "By active contacts since 2 March 2026. Pro from $39 a month for 2,500 contacts, reported by third-party guides." },
      },
    ],
  },
  honesty: [
    "Manychat blocks automated reading of its own pages, so its column comes from third-party guides written in 2026 and read on 2026-10-22. \"Not found\" means those guides didn't show it, not that Manychat lacks it.",
    "Our column is checked against our own code. Anything that depends on Meta, Shopify or a legal review says so.",
  ],
  sources: [
    { label: "Kanal: Manychat for Instagram", url: "https://getkanal.com/blog/manychat-instagram", checked: "2026-10-22" },
    { label: "Chatarmin: Manychat pricing 2026", url: "https://chatarmin.com/en/blog/manychat-pricing", checked: "2026-10-22" },
    { label: "Layer3 Labs: Manychat pricing 2026", url: "https://www.layer3labs.io/guides/manychat-pricing", checked: "2026-10-22" },
    { label: "DMChamp: Manychat pricing, contacts and AI costs", url: "https://dmchamp.com/resources/manychat-pricing-2026/", checked: "2026-10-22" },
    {
      label: "Manychat community: Share to DM trigger",
      url: "https://community.manychat.com/product-updates/reward-followers-for-sharing-your-posts-to-their-stories-7643",
      checked: "2026-10-22",
    },
    { label: "Mooon AI: Manychat review", url: "https://blog.mooonai.com/en/manychat", checked: "2026-10-22" },
    { label: "Zapier: Manychat integrations", url: "https://zapier.com/apps/manychat/integrations", checked: "2026-10-22" },
  ],
  related: [
    { label: "Switch from Manychat", href: "/switch-from-manychat" },
    { label: "Social Hood vs Interakt", href: "/compare/interakt" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Social Hood vs Interakt

export const COMPARE_INTERAKT: GtmPage = {
  path: "/compare/interakt",
  name: "Social Hood vs Interakt",
  title: "Social Hood vs Interakt",
  description:
    "A side-by-side of Social Hood and Interakt for sellers on WhatsApp and Instagram in India: campaigns, catalogue, AI, comments and publishing, with sources and the date they were read.",
  eyebrow: "Compare",
  h1: "Social Hood vs Interakt",
  intro:
    "Interakt is built around WhatsApp: bulk campaigns, catalogues and checkout. Social Hood is built around the conversation and the comment: an AI inbox, comment analysis and Instagram publishing. Here is the detail.",
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
          title: "Social Hood may fit better if",
          body: "your customers find you through Instagram posts and comments, and you want comments read and answered, replies drafted from your own knowledge and your posts scheduled in the same place.",
        },
      ],
    },
  ],
  compare: {
    competitor: "Interakt",
    caption: "Social Hood and Interakt feature by feature",
    rows: [
      {
        feature: "Channels",
        ours: { status: "yes", text: "WhatsApp and Instagram. Facebook waits on Meta's approval." },
        // source: interakt.shop/pricing, read 2026-10-25: Growth and Advanced list WhatsApp and Instagram; the Instagram-only Starter is shown at 999 rupees
        theirs: { status: "yes", text: "WhatsApp and Instagram, depending on the plan." },
      },
      {
        feature: "Bulk WhatsApp campaigns",
        ours: { status: "soon", text: "Broadcasts are built and open after our review of India's consent rules. Pro and Max only." },
        // source: interakt.shop/pricing, read 2026-10-25: one-time and ongoing campaigns with click and conversion tracking on Growth
        theirs: { status: "yes", text: "One-time and ongoing campaigns with click and conversion tracking." },
      },
      {
        feature: "Product catalogue",
        ours: { status: "yes", text: "Add products by hand or CSV; the AI answers price and stock from it. Shopify sync is coming soon. Pro and Max." },
        // source: interakt.shop/pricing, read 2026-10-25: catalogue creation and product message templates on Growth
        theirs: { status: "yes", text: "Catalogue creation and product message templates." },
      },
      {
        feature: "Payments and checkout in chat",
        ours: { status: "no", text: "Not yet. Payments are planned after the catalogue." },
        // source: docs/competitors.md (Hyperleap Interakt alternatives 2026; InstantDM vs Interakt; read 2026-10-22): checkout and WhatsApp Pay
        theirs: { status: "yes", text: "Checkout and WhatsApp Pay, according to third-party guides." },
      },
      {
        feature: "Comment to DM on Instagram",
        ours: { status: "yes", text: "Keyword or any comment, on chosen posts or all, with a private reply." },
        // source: docs/competitors.md at-a-glance table: comment and DM automation on Instagram (2026-10-22)
        theirs: { status: "yes", text: "Instagram automation is listed in the comparison guides." },
      },
      {
        feature: "AI answers from your knowledge",
        ours: { status: "yes", text: "Off, Suggest or Auto, with escalation rules and a list of unanswered questions." },
        // source: docs/competitors.md: "early (Haptik)" per third-party guides (2026-10-22)
        theirs: { status: "yes", text: "Described by third-party guides as early, through a partner." },
      },
      {
        feature: "Comment analysis per post",
        ours: { status: "yes", text: "Sentiment, topics, buying signals, spam and a summary." },
        // source: docs/competitors.md distinctive list: no competitor page read showed it (2026-10-22)
        theirs: { status: "not-found" },
      },
      {
        feature: "Publishing Instagram posts",
        ours: { status: "yes", text: "Images, carousels, Reels and Stories." },
        // source: docs/competitors.md at-a-glance: publishing not found for Interakt (2026-10-22)
        theirs: { status: "not-found" },
      },
      {
        feature: "Team inbox",
        ours: { status: "yes", text: "Roles, assignment, saved replies and business hours. Seats by plan." },
        // source: interakt.shop/pricing, read 2026-10-25: unlimited agents on Growth and Advanced; the page is inconsistent about roles
        theirs: { status: "yes", text: "Unlimited agents on higher plans; the pricing page is unclear about roles." },
      },
      {
        feature: "Starting price",
        ours: { status: "yes", text: "A Free plan with no card. Pro is priced in rupees on the pricing page." },
        // source: interakt.shop/pricing, read 2026-10-25: Starter 999 rupees (Instagram only), Growth 2,799, Advanced 3,799, plus taxes. Meta's WhatsApp fees are separate (docs/competitors.md).
        theirs: { status: "yes", text: "₹999 a month for Instagram only and ₹2,799 for WhatsApp and Instagram (Growth), plus taxes." },
      },
    ],
  },
  honesty: [
    "Interakt's column comes from its pricing page, read on 2026-10-25, and from third-party guides read on 2026-10-22. Its plans and prices change, so check interakt.shop before you decide.",
    "\"Not found\" means we didn't see it in what we read, not that Interakt lacks it.",
    "Neither company's plans include Meta's WhatsApp messaging fees, which Meta charges to your business.",
  ],
  sources: [
    { label: "Interakt pricing", url: "https://www.interakt.shop/pricing/", checked: "2026-10-25" },
    { label: "Hyperleap: Interakt alternatives 2026", url: "https://hyperleap.ai/comparison/best-interakt-alternatives-2026", checked: "2026-10-22" },
    { label: "InstantDM vs Interakt", url: "https://instantdm.com/vs/interakt", checked: "2026-10-22" },
    { label: "respond.io: Interakt review", url: "https://respond.io/blog/interakt-review", checked: "2026-10-22" },
  ],
  related: [
    { label: "Social Hood vs Manychat", href: "/compare/manychat" },
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
    "See what people say on each Instagram post: sentiment, topics, buying signals and spam, a summary per post and a needs-reply count. Reply, send a DM, hide or delete from one page.",
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
        { title: "You stay in charge", body: "Social Hood hides spam only when you turn that on. Nothing is deleted without you." },
      ],
    },
  ],
  honesty: ["Comment analysis needs your Instagram account connected, which depends on Meta's approval of Social Hood's app."],
  sources: [],
  related: [
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: "Publishing", href: "/features/publishing" },
    { label: "Social Hood vs Manychat", href: "/compare/manychat" },
  ],
  shot: "inbox",
};

export const FEATURE_AI_INBOX: GtmPage = {
  path: "/features/ai-inbox",
  name: "The AI inbox",
  title: "The AI inbox for Instagram and WhatsApp",
  description:
    "One inbox for Instagram DMs and WhatsApp chats. The AI drafts or sends replies from your own knowledge in English, Hindi and Hinglish, and hands over what it can't answer.",
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
        { title: "Only your knowledge", body: "Answers come from the documents, questions and products you add, in English, Hindi and Hinglish. When the answer isn't there it doesn't guess." },
        { title: "Escalation you can rely on", body: "Refunds, legal threats, complaints, abuse, low confidence, or your own phrases go to Needs you. Replying yourself pauses the AI." },
        { title: "Questions it couldn't answer", body: "Each unanswered question is recorded, so you know what to add to your knowledge." },
      ],
    },
    {
      id: "team",
      title: "Built for a team",
      items: [
        { title: "Assign, save replies, set hours", body: "Assign conversations, reuse saved replies and send an away message outside business hours." },
        { title: "Ask Social Hood", body: "Ask about your own posts, comments and conversations in plain words. Answers cite the figures they used, and anything it prepares waits for your approval." },
      ],
    },
  ],
  honesty: [
    "Instagram only allows a business to message within 24 hours of the customer's last message. Social Hood shows when the window closes.",
    "The AI uses credits from your monthly allowance. Plan limits are on the pricing page.",
  ],
  sources: [],
  related: [
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "Social Hood vs Interakt", href: "/compare/interakt" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  shot: "aiDraft",
};

export const FEATURE_PUBLISHING: GtmPage = {
  path: "/features/publishing",
  name: "Publishing",
  title: "Schedule Instagram posts and Stories",
  description:
    "Plan and schedule Instagram images, carousels, Reels and Stories from one calendar, with AI captions, a media library and hashtag groups, in the same app as your inbox.",
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
