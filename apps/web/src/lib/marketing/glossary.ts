/**
 * The glossary of Meta messaging terms (C-163): /glossary and /glossary/{slug}, rendered by
 * components/marketing/glossary. Rules for everything written here:
 *
 * - The definition is one plain sentence, first on the page, quotable on its own (it is also the
 *   meta description, so at most 155 characters).
 * - Every Meta rule comes from Meta's own pages (developers.facebook.com, facebook.com/business/help,
 *   help.instagram.com), listed in the term's `sources` with the date read. A comment above each
 *   detail paragraph names the source. Meta's help centres answer automated reads with an empty
 *   shell, so those were read through a search engine's copy (`via: "search"`), and the page says so.
 * - "How Amplychat handles it" is checked against the code (the path is named in a comment) and
 *   uses the comparison statuses: yes, coming soon, with Meta's approval, not offered.
 * - A term Meta's own docs don't define was dropped: knowledge base, keyword trigger and lead
 *   scoring (C-163).
 * - No numbers of ours that aren't in the code or plan table, no "best", no fake proof.
 */

import type { Status } from "./gtm-pages";

export const GLOSSARY_PATH = "/glossary";
/** When the glossary's copy last changed (the index's lastmod); each term has its own `updated`. */
export const GLOSSARY_UPDATED = "2026-10-31";

export type GlossaryChannel = "WhatsApp" | "Instagram" | "Meta";

export type GlossarySource = {
  label: string;
  url: string;
  /** ISO date the page was read. */
  checked: string;
  /** Read through a search engine's copy, because the page blocks automated reads. */
  via?: "search";
};

export type GlossaryHandling = { status: Status; title: string; body: string };

export type GlossaryTerm = {
  /** /glossary/{slug}: lowercase words and hyphens. */
  slug: string;
  /** The term as written, the page's h1. */
  term: string;
  /** Other names for it (an abbreviation, Meta's newer name), for DefinedTerm.alternateName. */
  aka?: string[];
  /** Which product the term belongs to. */
  channel: GlossaryChannel;
  /** The title tag before "· Amplychat": at most 49 characters. */
  title: string;
  /** One sentence, at most 155 characters: the lede and the meta description. */
  definition: string;
  /** The detail, a few short paragraphs from Meta's own docs. */
  detail: string[];
  /** How Amplychat handles it, true to the code today. */
  handling: GlossaryHandling[];
  /** Slugs of related terms. */
  related: string[];
  /** The guide or feature page that goes further. */
  learn: { label: string; href: string };
  sources: GlossarySource[];
  /** ISO date this term's copy last changed. */
  updated: string;
};

const READ = "2026-10-31";

// ---- Meta's pages, each read on 2026-10-31 (C-163)
const S = {
  pricing: { label: "WhatsApp: pricing", url: "https://developers.facebook.com/docs/whatsapp/pricing", checked: READ },
  templates: {
    label: "WhatsApp: message templates",
    url: "https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates",
    checked: READ,
  },
  optIn: { label: "WhatsApp: get opt-in for WhatsApp", url: "https://developers.facebook.com/docs/whatsapp/overview/getting-opt-in", checked: READ },
  embeddedSignup: { label: "WhatsApp: Embedded Signup", url: "https://developers.facebook.com/docs/whatsapp/embedded-signup", checked: READ },
  limits: { label: "WhatsApp: messaging limits", url: "https://developers.facebook.com/docs/whatsapp/messaging-limits", checked: READ },
  phoneNumbers: {
    label: "WhatsApp: business phone numbers",
    url: "https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/phone-numbers",
    checked: READ,
  },
  displayNames: { label: "WhatsApp: display names", url: "https://developers.facebook.com/docs/whatsapp/display-names", checked: READ },
  cloudApi: { label: "WhatsApp Cloud API: overview", url: "https://developers.facebook.com/docs/whatsapp/cloud-api/overview", checked: READ },
  aboutPlatform: {
    label: "About the WhatsApp Business Platform",
    url: "https://developers.facebook.com/documentation/business-messaging/whatsapp/about-the-platform",
    checked: READ,
  },
  solutionProviders: { label: "WhatsApp: solution providers", url: "https://developers.facebook.com/docs/whatsapp/solution-providers", checked: READ },
  coexistence: {
    label: "WhatsApp: onboard WhatsApp Business app users",
    url: "https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users/",
    checked: READ,
  },
  qualityRating: {
    label: "Meta Business Help: your WhatsApp number's quality rating",
    url: "https://www.facebook.com/business/help/896873687365001",
    checked: READ,
    via: "search",
  },
  businessVerification: {
    label: "Meta Business Help: verify your business",
    url: "https://www.facebook.com/business/help/2058515294227817",
    checked: READ,
    via: "search",
  },
  igMessaging: {
    label: "Instagram Platform: messaging API",
    url: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api",
    checked: READ,
  },
  privateReplies: { label: "Instagram Platform: private replies", url: "https://developers.facebook.com/docs/instagram-platform/private-replies", checked: READ },
  iceBreakers: {
    label: "Instagram Platform: ice breakers",
    url: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/ice-breakers",
    checked: READ,
  },
  quickReplies: {
    label: "Instagram Platform: quick replies",
    url: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/quick-replies",
    checked: READ,
  },
  webhookExamples: {
    label: "Instagram Platform: webhook examples",
    url: "https://developers.facebook.com/documentation/instagram-platform/webhooks/examples",
    checked: READ,
  },
  appReview: { label: "Instagram Platform: App Review", url: "https://developers.facebook.com/documentation/instagram-platform/app-review", checked: READ },
  messengerPolicy: {
    label: "Messenger Platform and Instagram Messaging API policy",
    url: "https://developers.facebook.com/documentation/business-messaging/messenger-platform/policy",
    checked: READ,
  },
  messageTags: { label: "Messenger Platform: message tags", url: "https://developers.facebook.com/docs/messenger-platform/message-tags/", checked: READ, via: "search" },
  igChangelog: {
    label: "Instagram Messaging changelog",
    url: "https://developers.facebook.com/documentation/business-messaging/instagram-messaging/changelog",
    checked: READ,
    via: "search",
  },
  professionalAccount: {
    label: "Instagram Help: set up a professional account",
    url: "https://help.instagram.com/502981923235522",
    checked: READ,
    via: "search",
  },
} satisfies Record<string, GlossarySource>;

const GUIDE_WHATSAPP = { label: "Guide: WhatsApp Business API vs app", href: "/guides/whatsapp-business-api-vs-app" };
const GUIDE_COMMENT_TO_DM = { label: "Guide: comment-to-DM automations", href: "/guides/comment-to-dm-automations" };
const GUIDE_IG_REPLIES = { label: "Guide: auto-reply to Instagram DMs", href: "/guides/instagram-dm-auto-replies" };

export const GLOSSARY: GlossaryTerm[] = [
  {
    slug: "24-hour-messaging-window",
    term: "24-hour messaging window",
    aka: ["Customer service window", "Standard messaging window"],
    channel: "Meta",
    title: "What is the 24-hour messaging window?",
    definition:
      "The 24-hour messaging window is the time after a customer's last message in which a business can reply freely on WhatsApp, Instagram or Messenger.",
    detail: [
      // source: WhatsApp pricing, read 2026-10-31: "a 24-hour timer called a customer service window starts"; each new user message resets it; templates are the only messages allowed outside it (message templates page)
      "On WhatsApp, Meta calls it the customer service window. When a customer messages you, a 24-hour timer starts, and each new message from them starts it again. Inside the window you can send any kind of message. Outside it, WhatsApp only lets you send an approved message template.",
      // source: Instagram messaging API, read 2026-10-31: "For most user actions, it lasts 24 hours"; a separate 7-day Human Agent window; Messenger policy: ads that start a chat can extend it up to 7 days
      "On Instagram and Messenger, Meta calls it the standard messaging window. For most actions it lasts 24 hours. A person on your team can answer later with the human agent tag, which gives a separate 7-day window, and a chat that starts from an ad can have a longer window.",
      "There are no templates on Instagram, so once the window has closed you wait for the customer to write again.",
    ],
    handling: [
      // source: services/reply_window.py (STANDARD_WINDOW, may_send), lib/inbox/format.ts windowChip, components/inbox/Composer.tsx
      {
        status: "yes",
        title: "Shows when the window closes",
        body: "Each conversation shows the time left in the window. When a WhatsApp window has closed, the composer offers an approved template instead.",
      },
      // source: services/sending.py (raise ApiError("reply_window_closed"))
      {
        status: "yes",
        title: "Never sends outside the rules",
        body: "Replies, automations and AI replies all pass the same check, so nothing is sent once a window has closed.",
      },
      { status: "yes", title: "Website chat has no window", body: "Your own website chat stays open, because Meta's rules don't apply to it." },
    ],
    related: ["human-agent-tag", "message-templates", "per-message-pricing"],
    learn: GUIDE_WHATSAPP,
    sources: [S.pricing, S.templates, S.igMessaging, S.messengerPolicy],
    updated: READ,
  },
  {
    slug: "human-agent-tag",
    term: "Human agent tag",
    aka: ["HUMAN_AGENT"],
    channel: "Instagram",
    title: "What is the human agent tag?",
    definition:
      "The human agent tag lets a person on a business's team answer an Instagram or Messenger message up to 7 days after the customer's last message.",
    detail: [
      // source: Instagram messaging API, read 2026-10-31: "your app can tag the response to use the separate 7-day Human Agent window"; Messenger policy: "allows businesses to manually respond to user messages within a separate 7-day period"
      "Instagram and Messenger normally allow replies for 24 hours after the customer's last message. The human agent tag opens a separate 7-day window, so a person can still answer a question that took longer to sort out.",
      // source: Messenger message tags (read through a search engine's copy, 2026-10-31): for human support issues that can't be resolved within 24 hours; automated messages aren't allowed; the app must be approved for the tag in App Review
      "Meta's rules say the tag is for a real person answering the customer, for example outside business hours or when an issue needs more time. Automated messages and anything unrelated to the customer's question aren't allowed with it. An app must be approved for the tag in Meta's App Review before it can use it.",
      "In practice it covers the reply that needs a check first: a refund to confirm, a delivery to trace, a question that arrived late on a Friday. It isn't a way to send offers after the window has closed.",
    ],
    handling: [
      // source: services/reply_window.py (HUMAN_AGENT_WINDOW, may_send only for kind "human"); settings.py ig_human_agent_enabled default False; platforms/instagram/adapter.py MESSAGE_TAG
      {
        status: "approval",
        title: "Built for replies you write yourself",
        body: "After 24 hours a reply you type is sent with the tag for up to 7 days, and the inbox shows the time left. It is switched on once Meta approves the tag for Amplychat.",
      },
      {
        status: "yes",
        title: "Never used by the AI or automations",
        body: "AI replies and automations stop when the 24-hour window closes. Only a person on your team can use the longer window.",
      },
    ],
    related: ["24-hour-messaging-window", "human-hand-off", "meta-app-review"],
    learn: GUIDE_IG_REPLIES,
    sources: [S.igMessaging, S.messengerPolicy, S.messageTags],
    updated: READ,
  },
  {
    slug: "message-templates",
    term: "Message templates",
    aka: ["WhatsApp templates", "Template messages"],
    channel: "WhatsApp",
    title: "What are WhatsApp message templates?",
    definition:
      "A WhatsApp message template is a message format Meta has approved in advance, and the only kind of message a business can send outside the 24-hour window.",
    detail: [
      // source: WhatsApp message templates, read 2026-10-31: "Template messages are the only type of message that can be sent to WhatsApp users outside of a customer service window"; status must be APPROVED
      "Templates are how a business starts or restarts a WhatsApp conversation. Meta's docs say template messages are the only type of message you can send to a customer outside the customer service window, and a template must have the status Approved before it can be sent.",
      // source: same page: "Each template must be categorized as authentication, marketing, or utility"; categories factor into pricing
      "Each template is filed under one of three categories: marketing, utility or authentication. The category decides what the template may say and what Meta charges when it is delivered.",
      "Templates can hold variables, such as a name or an order number, that are filled in when the message is sent. You create and submit them in WhatsApp Manager, and Meta reviews each one.",
    ],
    handling: [
      // source: platforms/whatsapp/adapter.py list_templates (GET message_templates only); components/inbox/TemplatePicker.tsx
      {
        status: "yes",
        title: "Send an approved template from the inbox",
        body: "When a window has closed, pick one of your approved templates in the conversation and fill in its text variables.",
      },
      {
        status: "no",
        title: "Templates are created in WhatsApp Manager",
        body: "Amplychat lists your approved templates; you create and submit new ones in Meta's WhatsApp Manager. Templates with a media header, button variables or named variables aren't listed yet.",
      },
      // source: services/broadcasts, settings.py broadcasts_enabled default False (O-11)
      { status: "soon", title: "Templates in broadcasts", body: "WhatsApp broadcasts are built and open after our review of consent rules." },
    ],
    related: ["template-categories", "24-hour-messaging-window", "opt-in"],
    learn: GUIDE_WHATSAPP,
    sources: [S.templates, S.pricing],
    updated: READ,
  },
  {
    slug: "template-categories",
    term: "Template categories",
    aka: ["Marketing, utility and authentication templates"],
    channel: "WhatsApp",
    title: "WhatsApp template categories explained",
    definition:
      "Template categories are WhatsApp's three template types, marketing, utility and authentication, which decide what a template may say and what Meta charges.",
    detail: [
      // source: WhatsApp pricing, read 2026-10-31: marketing = promotional template messages; utility = transactional or informational; authentication = identity verification; service = non-template replies in an open window
      "Meta's pricing page describes them this way. Marketing templates are promotional: an offer, a new product, a reminder to come back. Utility templates are transactional or informational, such as an order update or an appointment reminder. Authentication templates carry a code that verifies someone's identity.",
      // source: WhatsApp message templates, read 2026-10-31: each template must be categorized; categories factor into pricing
      "Every template must be filed under one of the three, and the category is part of what Meta charges for each delivered template message, together with the country of the person receiving it.",
      "Replies you write inside an open 24-hour window aren't templates. Meta counts them as service messages, which have their own pricing.",
      "Pick the category that matches what the message does, not the one you hope costs less: an order update is utility, a discount code is marketing, even when both go to a past customer.",
    ],
    handling: [
      // source: platforms/whatsapp/templates.py CATEGORIES
      {
        status: "yes",
        title: "Each template keeps its category",
        body: "The templates Amplychat lists from your account carry the category Meta gave them.",
      },
      // source: services/broadcasts/rates.py (estimate, "information, not a charge"); broadcasts off (O-11)
      {
        status: "soon",
        title: "A cost estimate before a broadcast",
        body: "Broadcasts, once they open, show an estimate of Meta's fees by category before you send. It is information only: Meta bills you.",
      },
      {
        status: "yes",
        title: "No markup on Meta's fees",
        body: "You pay Meta directly through your own WhatsApp Business account. Amplychat adds no markup.",
      },
    ],
    related: ["message-templates", "per-message-pricing", "opt-in"],
    learn: { label: "Plans and limits", href: "/pricing" },
    sources: [S.pricing, S.templates],
    updated: READ,
  },
  {
    slug: "opt-in",
    term: "Opt-in",
    aka: ["WhatsApp opt-in", "Consent"],
    channel: "WhatsApp",
    title: "What does opt-in mean on WhatsApp?",
    definition:
      "Opt-in is a person's permission for a business to message them on WhatsApp, which Meta requires before the business sends them anything.",
    detail: [
      // source: WhatsApp get opt-in, read 2026-10-31: "Businesses are required to obtain opt-in before messaging people on WhatsApp"
      "Meta's rule is short: businesses must get opt-in before messaging people on WhatsApp. The person has to have given you their number and agreed to hear from you.",
      // source: same page: state clearly that the person is opting in to receive messages, and the business's name; comply with applicable law
      "The request has to be clear. It must say that the person is opting in to messages, and name the business they will come from. Businesses must also follow the law where they and their customers are, which can ask for more than Meta does.",
      "Opt-in matters most for marketing. People who didn't expect your messages block or report them, and that lowers your number's quality rating.",
      "Keep a record of how and when each person agreed, so you can show it if you're asked.",
    ],
    handling: [
      // source: models/contacts.py ContactConsent (channel, purpose, status, source, evidence, occurred_at)
      {
        status: "yes",
        title: "A consent record on every contact",
        body: "Each contact keeps a history of when they agreed or withdrew, on which channel, and how: an Instagram opt-in, a flow question, a reply or a teammate's note.",
      },
      // source: services/broadcasts/stop.py, services/ingest.py
      {
        status: "yes",
        title: "STOP is respected",
        body: "A WhatsApp message that only says stop, unsubscribe or a similar phrase records that the person opted out.",
      },
      // source: services/broadcasts/audience.py, dispatch.py consent_skip; broadcasts off (O-11)
      {
        status: "soon",
        title: "Broadcasts check consent twice",
        body: "Broadcasts, once they open, go only to people with consent on file and check again just before each send.",
      },
    ],
    related: ["message-templates", "quality-rating", "template-categories"],
    learn: { label: "Safety and Meta's limits", href: "/safety" },
    sources: [S.optIn],
    updated: READ,
  },
  {
    slug: "whatsapp-business-account",
    term: "WhatsApp Business Account (WABA)",
    aka: ["WABA", "WhatsApp account"],
    channel: "WhatsApp",
    title: "What is a WhatsApp Business Account (WABA)?",
    definition:
      "A WhatsApp Business Account (WABA) is a business's account on the WhatsApp Business Platform: it holds its phone numbers, display name and templates.",
    detail: [
      // source: About the WhatsApp Business Platform, read 2026-10-31: a WhatsApp account is "Your business presence on WhatsApp. Contains your phone numbers, display name, usernames, and partner access configuration."
      "Meta describes it as your business presence on WhatsApp. It contains your business phone numbers, your display name and which partners can use it. Message templates belong to the account too.",
      // source: Embedded Signup, read 2026-10-31: customers "select an existing WhatsApp account (WAAC) or create a new one"; waba_id now denotes the Messaging account ID, value unchanged
      "Meta's newer docs also call it a WhatsApp account or a Messaging account; the ID apps use for it, the waba_id, is unchanged. A WABA sits inside a business portfolio in Meta Business Suite, and some limits, such as messaging limits, are set at the portfolio level.",
      "It isn't the same as the WhatsApp Business app on a phone: a WABA is used through the platform's API and apps built on it.",
      "One business can have more than one WABA, for example one per brand, and each can hold several phone numbers. Whoever runs the business portfolio decides which apps can use it.",
    ],
    handling: [
      // source: lib/whatsapp/embedded-signup.ts, services/whatsapp_connect.py, services/broadcasts/rates.py docstring
      {
        status: "yes",
        title: "The account stays yours",
        body: "You connect through Meta's Embedded Signup, which creates or picks the WhatsApp Business Account in your own business portfolio. Disconnecting Amplychat leaves it with you.",
      },
      {
        status: "yes",
        title: "Your payment method, no markup",
        body: "Meta bills the payment method on your account for messaging fees. No money for Meta's fees passes through Amplychat.",
      },
    ],
    related: ["embedded-signup", "whatsapp-cloud-api", "whatsapp-display-name"],
    learn: GUIDE_WHATSAPP,
    sources: [S.aboutPlatform, S.embeddedSignup, S.limits],
    updated: READ,
  },
  {
    slug: "whatsapp-cloud-api",
    term: "WhatsApp Cloud API",
    aka: ["WhatsApp Business Platform", "WhatsApp Business API"],
    channel: "WhatsApp",
    title: "What is the WhatsApp Cloud API?",
    definition:
      "The WhatsApp Cloud API is the WhatsApp Business Platform's API for sending and receiving WhatsApp messages from software instead of a phone.",
    detail: [
      // source: WhatsApp Cloud API overview, read 2026-10-31: "The WhatsApp Business Platform enables businesses to communicate with customers at scale"; Cloud API "enables you to programmatically message and call on WhatsApp"; requests go to graph.facebook.com
      "Meta says the WhatsApp Business Platform lets businesses talk to customers at scale, and the Cloud API is how software messages and calls on WhatsApp. Requests go to Meta's own Graph API, so there is no server of your own to run.",
      "People often call it the WhatsApp Business API. It is different from the free WhatsApp Business app: the app is for one phone and a few people, the platform is for a team, automation and other software.",
      // source: WhatsApp pricing, read 2026-10-31: per-message pricing; templates outside the window (message templates page)
      "The platform has its own rules: replies are free-form inside the 24-hour window, templates are needed outside it, and Meta charges per message by category and country.",
      "Most businesses reach it through an app built on the platform, such as an inbox or a help desk, rather than by writing code themselves.",
    ],
    handling: [
      // source: platforms/whatsapp/graph.py (graph.facebook.com), platforms/whatsapp/adapter.py POST {phone_number_id}/messages
      {
        status: "yes",
        title: "Built on the Cloud API",
        body: "Amplychat sends and receives WhatsApp messages through Meta's Cloud API, and they arrive in the same inbox as Instagram and website chat.",
      },
      {
        status: "yes",
        title: "AI replies and automations on WhatsApp",
        body: "The AI drafts or sends replies from your own knowledge inside the window, and hands the rest to a person.",
      },
    ],
    related: ["whatsapp-business-account", "embedded-signup", "whatsapp-coexistence"],
    learn: GUIDE_WHATSAPP,
    sources: [S.cloudApi, S.aboutPlatform, S.pricing],
    updated: READ,
  },
  {
    slug: "embedded-signup",
    term: "Embedded Signup",
    channel: "WhatsApp",
    title: "What is WhatsApp Embedded Signup?",
    definition:
      "Embedded Signup is Meta's sign-in window that lets a business create or pick its WhatsApp Business Account and add its number from inside another app.",
    detail: [
      // source: Embedded Signup, read 2026-10-31: "an authentication and authorization interface that is compatible with desktop and mobile"; customers select an existing WhatsApp account or create one, and enter and verify their business phone number
      "Meta describes Embedded Signup as an authentication and authorization interface that works on desktop and mobile. A business opens it from the app it wants to use, logs in with Meta, chooses an existing WhatsApp account or creates a new one, and enters and verifies its business phone number.",
      // source: WhatsApp solution providers, read 2026-10-31: Tech Providers' clients add their own payment method after onboarding and Meta bills them
      "At the end, the business has given that app access to its account. Under the Tech Provider model, the business adds its own payment method and Meta bills it for messaging.",
      "For the business it replaces a long manual setup with a few screens, and the account stays in the business's own name.",
    ],
    handling: [
      // source: lib/whatsapp/embedded-signup.ts (FB.login with config_id), components/connections/ConnectWhatsAppButton.tsx, platforms/whatsapp/signup.py
      {
        status: "yes",
        title: "Connect WhatsApp in a few steps",
        body: "Connect WhatsApp in Amplychat opens Meta's Embedded Signup. When it finishes, Amplychat subscribes to your account's messages and your number appears in the inbox.",
      },
      {
        status: "yes",
        title: "No password shared",
        body: "You log in with Meta, not with Amplychat, and you choose what to share.",
      },
      // source: services/whatsapp_connect.py (Meta may refuse when the weekly onboarding allowance is used up)
      {
        status: "approval",
        title: "Meta can pause new sign-ups",
        body: "Meta limits how many businesses an app can connect each week. If Meta refuses a sign-up for that reason, Amplychat says so and you can try again later.",
      },
    ],
    related: ["whatsapp-business-account", "business-solution-provider", "whatsapp-coexistence"],
    learn: { label: "How it works", href: "/how-it-works" },
    sources: [S.embeddedSignup, S.solutionProviders],
    updated: READ,
  },
  {
    slug: "business-solution-provider",
    term: "Business Solution Provider (BSP)",
    aka: ["BSP", "Solution Partner", "Tech Provider"],
    channel: "WhatsApp",
    title: "What is a WhatsApp Business Solution Provider?",
    definition:
      "A Business Solution Provider (BSP) is a Meta partner that offers WhatsApp Business Platform services to businesses; Meta now calls it a Solution Partner.",
    detail: [
      // source: WhatsApp solution providers, read 2026-10-31: "Solution Partners are Meta Business Partners that provide a full range of WhatsApp Business Platform services"
      "BSP is the older, widely used name. Meta's current docs say Solution Partners are Meta Business Partners that provide a full range of WhatsApp Business Platform services to other businesses.",
      // source: same page: "Unlike Solution Partners, however, Tech Providers do not have credit lines"; Tech Providers' clients add their own payment method and Meta bills them
      "Meta also has Tech Providers: companies whose software uses the platform for their customers. The difference is billing. A Solution Partner can extend a credit line and invoice its clients for messaging. A Tech Provider can't, so each client adds its own payment method and Meta bills the client directly.",
      "When you compare WhatsApp tools, ask who bills you for Meta's fees, and whether anything is added on top.",
      "Either way, the business still needs its own WhatsApp Business Account and must follow Meta's rules on opt-in, templates and the 24-hour window. A partner can make setup easier, but it doesn't change what WhatsApp allows you to send.",
    ],
    handling: [
      // source: services/broadcasts/rates.py docstring (each WABA carries its own payment method, no markup, no money through Amplychat); no Solution Partner claim in code or copy
      {
        status: "no",
        title: "Amplychat doesn't resell messaging",
        body: "Amplychat doesn't invoice you for Meta's fees or extend credit. Your WhatsApp Business Account carries your own payment method, and Meta bills you.",
      },
      {
        status: "yes",
        title: "No markup on Meta's fees",
        body: "Our plans cover Amplychat. Meta's messaging fees are separate and paid to Meta, with nothing added.",
      },
    ],
    related: ["embedded-signup", "per-message-pricing", "whatsapp-business-account"],
    learn: { label: "Plans and limits", href: "/pricing" },
    sources: [S.solutionProviders],
    updated: READ,
  },
  {
    slug: "whatsapp-display-name",
    term: "Display name",
    aka: ["WhatsApp display name"],
    channel: "WhatsApp",
    title: "What is a WhatsApp display name?",
    definition:
      "A WhatsApp display name is the business name shown on a business phone number's WhatsApp profile, and sometimes at the top of its chats.",
    detail: [
      // source: WhatsApp business phone numbers, read 2026-10-31: "The display name appears in your business phone number's WhatsApp profile, and can also appear at the top of individual chat threads and the chat list if certain conditions are met"
      "Meta's docs say the display name appears on your business phone number's WhatsApp profile, and can also appear at the top of chats and in the chat list when certain conditions are met.",
      // source: same page: display name information is required when registering a number; statuses APPROVED, DECLINED, PENDING_REVIEW, AVAILABLE_WITHOUT_REVIEW; display names page: verification against the display name guidelines when the number reaches a higher messaging limit
      "You give a display name when you register a number for the platform. Meta reviews it against its display name guidelines, so it can be approved, declined, under review, or usable without review. A name that was usable without review is checked again when the number reaches a higher messaging limit.",
      "Choose the name customers know you by. A declined name means another request.",
      "The display name is separate from the rest of your WhatsApp profile, such as the description, website and photo. Changing the name means a new request and a new review, so settle on it before you message customers at scale, and keep it close to the name on your website and shop.",
    ],
    handling: [
      // source: platforms/whatsapp/signup.py NUMBER_FIELDS (verified_name); settings and connections pages show the number's name or phone number
      {
        status: "yes",
        title: "Read when you connect",
        body: "Amplychat reads your number and its name from Meta when you connect.",
      },
      {
        status: "no",
        title: "Changed in WhatsApp Manager",
        body: "Amplychat doesn't edit or submit display names; you request a change in Meta's WhatsApp Manager.",
      },
    ],
    related: ["whatsapp-business-account", "messaging-limits", "business-verification"],
    learn: GUIDE_WHATSAPP,
    sources: [S.phoneNumbers, S.displayNames],
    updated: READ,
  },
  {
    slug: "quality-rating",
    term: "Quality rating",
    aka: ["WhatsApp quality rating"],
    channel: "WhatsApp",
    title: "What is a WhatsApp quality rating?",
    definition:
      "A WhatsApp quality rating is Meta's score of how people received a business's recent messages: green for high, yellow for medium and red for low quality.",
    detail: [
      // source: About the WhatsApp Business Platform, read 2026-10-31: "Assigned per business phone number and per template, and used to determine automatic throughput tier upgrades"
      "Meta gives a quality rating to each business phone number and to each template. It is one of the things Meta looks at before raising a number's limits.",
      // source: Meta Business Help "About your WhatsApp Business phone number's quality rating", read through a search engine's copy on 2026-10-31 (the help centre blocks automated reads): based on messages received over the past 7 days, with blocks, reports and the reasons people give; green high, yellow medium, red low; shown in WhatsApp Manager
      "Meta's help centre says the rating reflects the messages people received over the last 7 days, and weighs signals such as blocks and reports, including the reasons people give when they block. Green means high quality, yellow medium and red low. You can see it in WhatsApp Manager.",
      // source: WhatsApp messaging limits, read 2026-10-31: automatic scaling needs high-quality messages across numbers and templates
      "A low rating can hold back a higher messaging limit. Messages people asked for, sent at a sensible pace, keep it healthy. Templates have their own quality too, so watch how people receive each one and retire the ones they don't like.",
    ],
    handling: [
      // source: platforms/whatsapp/health.py, services/broadcasts/health.py, components/broadcasts/BroadcastComposer.tsx
      {
        status: "soon",
        title: "Broadcasts watch the rating",
        body: "Broadcasts, once they open, warn you when the rating drops to medium and pause when it falls.",
      },
      // source: services/sending.py enqueue_send, platforms/buckets.py
      {
        status: "yes",
        title: "Sends go through a queue",
        body: "Every message waits in a send queue paced for Meta's limits, so a busy day doesn't flood your customers.",
      },
      {
        status: "yes",
        title: "Consent on every contact",
        body: "Each contact keeps a consent record, and STOP replies are recorded as opt-outs.",
      },
    ],
    related: ["messaging-limits", "opt-in", "whatsapp-display-name"],
    learn: { label: "Safety and Meta's limits", href: "/safety" },
    sources: [S.aboutPlatform, S.qualityRating, S.limits],
    updated: READ,
  },
  {
    slug: "messaging-limits",
    term: "Messaging limits",
    aka: ["WhatsApp messaging tiers"],
    channel: "WhatsApp",
    title: "What are WhatsApp messaging limits?",
    definition:
      "WhatsApp messaging limits cap how many different people a business can message outside the 24-hour window in a rolling 24 hours, starting at 250.",
    detail: [
      // source: WhatsApp messaging limits, read 2026-10-31: "the maximum number of unique WhatsApp user phone numbers your business can deliver messages to" outside customer service windows in a rolling 24 hours; new portfolios start at 250; then 2,000, 10,000, 100,000 or unlimited
      "The limit counts unique people you message outside an open customer service window, in a rolling 24-hour period. Replies inside a window don't count. New business portfolios start at 250 people a day, and the levels above are 2,000, 10,000, 100,000 and unlimited.",
      // source: same page: set at the business portfolio level and shared by all numbers in it
      "The limit is set for your whole business portfolio and shared by all its numbers, so one number can use all of it.",
      // source: same page: to 2,000 by verifying the business or sending 2,000 delivered messages outside windows in 30 days with high-quality templates; then automatic scaling when quality is high and at least half the limit was used in 7 days
      "To reach 2,000, Meta lists verifying your business, or sending 2,000 messages outside windows within 30 days with high-quality templates. Above that, Meta raises the limit one level at a time when your messages are high quality and you have used at least half of your limit in the last 7 days.",
      "For most small businesses replies matter more than limits, because replies inside a window don't count.",
    ],
    handling: [
      // source: services/sending.py, platforms/buckets.py (per-account send rates)
      {
        status: "yes",
        title: "A paced send queue",
        body: "Every message goes through a queue paced per account, and a send that would go over the rate waits its turn.",
      },
      // source: services/broadcasts/throttle.py, health.py (unverified against a live number); broadcasts off (O-11)
      {
        status: "soon",
        title: "Broadcasts within your limit",
        body: "Broadcasts, once they open, read your number's limit from Meta, pace sends to it and pause if Meta lowers it.",
      },
    ],
    related: ["quality-rating", "business-verification", "message-templates"],
    learn: { label: "Safety and Meta's limits", href: "/safety" },
    sources: [S.limits],
    updated: READ,
  },
  {
    slug: "per-message-pricing",
    term: "Per-message pricing",
    aka: ["WhatsApp pricing", "Meta's WhatsApp fees"],
    channel: "WhatsApp",
    title: "How WhatsApp per-message pricing works",
    definition:
      "Per-message pricing is how Meta charges for the WhatsApp Business Platform: a fee for each delivered message, by its category and the recipient's country.",
    detail: [
      // source: WhatsApp pricing, read 2026-10-31: "Effective July 1, 2025 – Meta charges on a per-message basis"; by category and market; no charge for user-to-business messages
      "Since 1 July 2025 Meta has charged per message. The fee depends on the message's category (marketing, utility, authentication or service) and the country of the person receiving it. Messages customers send you are free.",
      // source: same page: from 1 October 2026 Meta resumed charging for service messages; each business phone number has 1,000 free service messages a month, no roll-over; charged from the 1,001st
      "Service messages are your free-form replies inside the 24-hour window. Since 1 October 2026 Meta charges for them again, after a free allowance: each business phone number gets 1,000 free service messages a month, which don't roll over.",
      // source: same page: a reply in the window after a Click to WhatsApp ad can open a free entry point window of up to 7 days, with no charge for messages in it
      "When a chat starts from a Click to WhatsApp ad, Meta can open a free entry point window of up to 7 days in which it doesn't charge for messages. Meta's rate card lists the prices by country.",
      "The person messaging you pays nothing. The business pays Meta, either through the payment method on its own WhatsApp Business Account or through a partner that bills it, so ask any tool you use how its plan and Meta's fees fit together.",
    ],
    handling: [
      // source: components/marketing/WhatsAppCharges.tsx, ai-info page, terms page (owner, 2026-10-29)
      {
        status: "yes",
        title: "You pay Meta directly",
        body: "You pay Meta directly through your own WhatsApp Business account. Amplychat adds no markup.",
      },
      {
        status: "yes",
        title: "Instagram has no such charge",
        body: "Meta doesn't charge per message for Instagram DMs, so this applies to WhatsApp only.",
      },
    ],
    related: ["template-categories", "24-hour-messaging-window", "business-solution-provider"],
    learn: { label: "Plans and limits", href: "/pricing" },
    sources: [S.pricing],
    updated: READ,
  },
  {
    slug: "business-verification",
    term: "Business verification",
    aka: ["Meta business verification"],
    channel: "Meta",
    title: "What is Meta business verification?",
    definition:
      "Business verification is Meta's check that a business portfolio belongs to a real business, which unlocks higher WhatsApp limits and more phone numbers.",
    detail: [
      // source: About the WhatsApp Business Platform, read 2026-10-31: "Business portfolios can be verified, and verification status factors into improved functionality, such as higher throughput"
      "Meta verifies business portfolios in Meta Business Suite. Meta's WhatsApp docs say verification status counts toward improved functionality, such as higher throughput.",
      // source: WhatsApp business phone numbers, read 2026-10-31: new portfolios capped at two registered numbers, raised to 20 automatically once verified or at a 2,000 messaging limit; messaging limits page: verifying is one way to reach 2,000
      "It has concrete effects on WhatsApp. A new portfolio can register two business phone numbers, and Meta raises that to 20 once the business is verified or reaches the 2,000 messaging limit. Verifying is also one of the ways to reach that 2,000 limit.",
      // source: Meta Business Help "Verify your business", read through a search engine's copy on 2026-10-31: business verification is not the same as Meta Verified and gives no badge
      "Meta's help centre notes that business verification is not the same as Meta Verified, and doesn't give you a badge.",
      "You verify in Meta Business Suite with your business's details and documents, and Meta gives its decision there. It is worth doing early, because Meta's limits start low for a portfolio it hasn't verified, and the review can take a while to come back.",
    ],
    handling: [
      {
        status: "no",
        title: "Done in Meta Business Suite",
        body: "Verification is between your business and Meta. Amplychat doesn't submit documents for you, and you can start on WhatsApp before it is done.",
      },
      {
        status: "yes",
        title: "Your limits apply as Meta sets them",
        body: "Amplychat sends within whatever limit Meta gives your portfolio, through a paced send queue.",
      },
    ],
    related: ["messaging-limits", "whatsapp-display-name", "meta-app-review"],
    learn: GUIDE_WHATSAPP,
    sources: [S.aboutPlatform, S.phoneNumbers, S.limits, S.businessVerification],
    updated: READ,
  },
  {
    slug: "whatsapp-coexistence",
    term: "WhatsApp Business app coexistence",
    aka: ["Coexistence"],
    channel: "WhatsApp",
    title: "What is WhatsApp Business app coexistence?",
    definition:
      "Coexistence lets a business keep using the WhatsApp Business app on its phone while the same number is also connected to the WhatsApp Business Platform.",
    detail: [
      // source: WhatsApp "Onboard WhatsApp Business app users", read 2026-10-31: Embedded Signup can "allow business customers to onboard using their existing WhatsApp Business app account and phone number"; they "can use your app to send high volumes of messages"
      "Meta's docs describe it as letting businesses onboard to the platform with their existing WhatsApp Business app account and number. After that, the business can send messages at volume through a platform app, while still chatting one to one in the app on the phone.",
      // source: same page (requirements, read through a search engine's summary of it on 2026-10-31): the provider must be a Solution Partner or Tech Provider and use Embedded Signup; messages sent from the app stay free while Cloud API messages follow Cloud API pricing
      "Only Solution Partners and Tech Providers can offer it, through Embedded Signup. Messages sent from the phone app stay free, while messages sent through the platform follow its pricing.",
      "Without coexistence, moving a number to the platform means it no longer works in the WhatsApp Business app.",
      "Coexistence suits a small team that already chats with customers from a phone and wants automation or a shared inbox on top, without changing the number customers know. There are trade-offs, so read Meta's page on what is synced, what isn't and what each side costs before you switch, and check that your app version is recent enough.",
    ],
    handling: [
      // source: lib/whatsapp/embedded-signup.ts (FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING accepted as a finish); no history sync or echo webhooks (C-153 wording)
      {
        status: "no",
        title: "Not supported yet",
        body: "Amplychat doesn't offer coexistence today: it doesn't sync messages you send from the phone app. Use a number that isn't on the WhatsApp Business app.",
      },
    ],
    related: ["embedded-signup", "whatsapp-cloud-api", "whatsapp-business-account"],
    learn: GUIDE_WHATSAPP,
    sources: [S.coexistence],
    updated: READ,
  },
  {
    slug: "private-replies",
    term: "Private replies",
    aka: ["Instagram private reply"],
    channel: "Instagram",
    title: "What are Instagram private replies?",
    definition:
      "A private reply is a direct message a business sends to someone who commented on its Instagram post, Reel, story, Live or ad, in reply to that comment.",
    detail: [
      // source: Instagram private replies, read 2026-10-31: DM to someone who commented on a professional account's post, reel, story, Live or ad post; Inbox if they follow, Requests folder if not
      "Private replies are how a comment turns into a conversation. The message goes to the commenter's inbox if they follow you, or to their message requests if they don't.",
      // source: same page: "within 7 days of the creation time of the comment" (Live: only during the broadcast); "Only one message can be sent to the commenter"; "Follow-up messages can only be sent if the recipient responds, and must be sent within 24 hours of the response"
      "Meta sets three rules. You can send a private reply within 7 days of the comment, or only during the broadcast for a Live. Only one message can be sent for each comment. Further messages are allowed only once the person replies, and only within 24 hours of their reply.",
      "That is why good comment-to-DM flows ask for a tap first: the tap is a reply, and it opens the normal 24-hour window.",
    ],
    handling: [
      // source: services/comments/actions.py (ONE_PER_COMMENT, PRIVATE_REPLY_LIMIT = 7 days), services/automations/queue.py (skipped_expired)
      {
        status: "yes",
        title: "Both rules enforced",
        body: "Amplychat sends one private reply per comment, and never after 7 days. A second try says the comment already has one.",
      },
      {
        status: "yes",
        title: "From an automation or by hand",
        body: "Send one from a comment-to-DM automation or from the comments page, next to a public reply, hide or delete.",
      },
      // source: platforms/buckets.py IG_PRIVATE_REPLY
      { status: "yes", title: "Paced for Meta's limits", body: "Private replies go through the send queue at a pace Meta allows, so a viral post doesn't stall." },
    ],
    related: ["comment-to-dm", "quick-replies", "24-hour-messaging-window"],
    learn: GUIDE_COMMENT_TO_DM,
    sources: [S.privateReplies],
    updated: READ,
  },
  {
    slug: "comment-to-dm",
    term: "Comment-to-DM",
    aka: ["Comment to DM automation"],
    channel: "Instagram",
    title: "What is comment-to-DM on Instagram?",
    definition:
      "Comment-to-DM is an automation that sends a direct message to everyone who comments a keyword on an Instagram post, using Meta's private replies.",
    detail: [
      // source: Instagram private replies, read 2026-10-31: one private reply per comment, within 7 days; follow-ups only after the person responds, within 24 hours
      "Comment-to-DM is the common name for an automation built on Meta's private replies. Someone comments a word such as LINK, and the account answers in their DMs with the link, a price or a question. Meta's rules apply to every message: one private reply per comment, within 7 days of the comment, and nothing more until the person replies.",
      // source: Instagram quick replies, read 2026-10-31: a preset button a user taps to reply; not available on desktop
      "A tap on a button counts as a reply, so many automations open with a short question and a quick reply button, then send the link once the person taps.",
      // source: Messenger Platform and Instagram Messaging API policy, read 2026-10-31 (the platform policy for Instagram messaging)
      "Meta's platform policy applies to the messages, so they should be what the commenter asked for.",
    ],
    handling: [
      // source: models/automations.py (PostScope all/selected/next_post, MatchMode word/exact/contains), services/automations/actions.py (public_reply_texts)
      {
        status: "yes",
        title: "Any post, chosen posts or the next post",
        body: "Match a keyword as a word, exactly or anywhere in the comment, or answer any comment, with random public replies under the post.",
      },
      // source: FR-AUT-21 tap-first (RunResult.AWAITING_REPLY); services/automations/nudge.py
      {
        status: "yes",
        title: "Tap first, and a follow nudge that never gates",
        body: "The DM can ask for a tap before the link. A separate invitation to follow never holds the link back.",
      },
      // source: gtm-pages.ts SWITCH_PAGE (Live comments built, wait on Meta); lib/marketing/plan-table.json active_automations 3/50/unlimited
      {
        status: "approval",
        title: "Live comments",
        body: "Comment automations on Lives are built and reach your account once Meta's approval for Amplychat is complete. Free includes 3 active automations.",
      },
    ],
    related: ["private-replies", "quick-replies", "story-mentions"],
    learn: GUIDE_COMMENT_TO_DM,
    sources: [S.privateReplies, S.quickReplies, S.messengerPolicy],
    updated: READ,
  },
  {
    slug: "ice-breakers",
    term: "Ice breakers",
    aka: ["Conversation starters"],
    channel: "Instagram",
    title: "What are Instagram ice breakers?",
    definition:
      "Ice breakers are up to four questions a business sets that people can tap to start a conversation when they open its Instagram or Messenger chat.",
    detail: [
      // source: Instagram ice breakers, read 2026-10-31: "Ice Breakers provide a way for your app users to start a conversation with a business"; a list of frequently asked questions; "A maximum of 4 questions"; "not available on desktop"
      "Meta describes ice breakers as a way for people to start a conversation with a business, using a list of frequently asked questions. An account can set at most four, and they don't show on desktop.",
      "When someone taps one, the business receives it as a message, which opens the usual 24-hour window. Good ice breakers are the questions you already answer every day: prices, delivery, opening hours, how to book.",
      // source: Instagram messaging API, read 2026-10-31: messages from a professional account; the 24-hour window
      "They are set through the messaging API on a professional account, and an app can answer each one differently.",
      "They help most with new customers who don't know yet what to ask you, and they cut the first back-and-forth short. Keep each question short enough to read at a glance, and make sure each one has a clear, ready answer behind it, from an automation or from your own knowledge.",
    ],
    handling: [
      // source: services/ice_breakers.py (up to 4, 80-character questions), platforms/instagram/profile.py (messenger_profile, request shape unverified until T0.9)
      {
        status: "yes",
        title: "Up to four starters",
        body: "Write up to four questions in Amplychat and they are set on your Instagram account.",
      },
      {
        status: "yes",
        title: "An automation or the AI answers",
        body: "A tap can start an automation, or the AI answers from your knowledge.",
      },
    ],
    related: ["quick-replies", "24-hour-messaging-window", "instagram-messaging-api"],
    learn: GUIDE_IG_REPLIES,
    sources: [S.iceBreakers, S.igMessaging],
    updated: READ,
  },
  {
    slug: "quick-replies",
    term: "Quick replies",
    channel: "Instagram",
    title: "What are quick replies on Instagram?",
    definition:
      "Quick replies are preset buttons under a business's Instagram message that the customer taps to answer, instead of typing.",
    detail: [
      // source: Instagram quick replies, read 2026-10-31: "A Quick Reply is a preset button that allows a user to quickly reply to a prompt or question"; at most 13; up to 20 characters before truncation; plain text only; not available on desktop
      "Meta defines a quick reply as a preset button that lets someone answer a question in one tap. A message can carry up to 13, each shows about 20 characters before it is cut off, and only plain text is supported. They don't show on desktop.",
      "A tap is sent as the customer's reply. That matters for comment-to-DM, where Meta allows only one private reply until the person answers: a tap counts as an answer.",
      "Keep the labels short and clear, and still handle typed answers, because people on a computer won't see the buttons.",
      "Quick replies suit one clear choice at a time: a size, a yes or no, a topic. For a link that should stay in the chat, use a link button instead. A short question above the buttons tells people what to pick and why.",
    ],
    handling: [
      // source: schemas/flows.py SendStep quick_replies (up to 13); platforms/instagram/adapter.py MAX_QUICK_REPLIES
      {
        status: "yes",
        title: "In every flow",
        body: "A flow message can offer quick replies, wait for the tap and go to that option's next step. Typed answers have their own path.",
      },
      // source: platforms/whatsapp/adapter.py (no reply buttons)
      {
        status: "no",
        title: "WhatsApp reply buttons",
        body: "On WhatsApp, Amplychat sends text, media, templates and product messages, not reply buttons.",
      },
    ],
    related: ["comment-to-dm", "private-replies", "ice-breakers"],
    learn: GUIDE_COMMENT_TO_DM,
    sources: [S.quickReplies],
    updated: READ,
  },
  {
    slug: "story-mentions",
    term: "Story mentions and replies",
    aka: ["Story mention", "Story reply"],
    channel: "Instagram",
    title: "Instagram story mentions and replies explained",
    definition:
      "A story mention is when someone tags a business in their Instagram story; a story reply is a DM sent in answer to the business's own story.",
    detail: [
      // source: Instagram webhook examples, read 2026-10-31: story_mention is a supported attachment type; a story reply arrives with reply_to set to an object with a story object including the URL of the story and the story ID
      "Both arrive in the business's DMs. Meta's webhook docs list a story mention as a message attachment of type story_mention, and a story reply as a message with a link to the story and its ID.",
      // source: Instagram messaging API, read 2026-10-31: the 24-hour window for most user actions
      "Either one is a message from the customer, so it opens the usual 24-hour window, and the business can answer in the same chat. A story reply often asks about what was in the story, a price, a size or a link, so it is a good moment for an automation or a quick answer.",
      "Stories disappear after 24 hours, so the link to the story stops working once it has gone. Mentions are a good moment to thank someone or share their story, with their permission.",
    ],
    handling: [
      // source: models/automations.py Trigger story_reply (GR-06), story_mention (GR-07)
      {
        status: "yes",
        title: "Automations for both",
        body: "A reply to your story or a mention can start an automation. Story replies can be limited to chosen stories, and a heart alone starts nothing.",
      },
      // source: services/story_mentions.py, components/comments/MentionsPage.tsx
      {
        status: "yes",
        title: "A list of mentions",
        body: "Mentions are listed on their own page. The story link is kept only while the story is live, and the media is never downloaded.",
      },
    ],
    related: ["comment-to-dm", "24-hour-messaging-window", "instagram-messaging-api"],
    learn: { label: "For creators", href: "/for-creators" },
    sources: [S.webhookExamples, S.igMessaging],
    updated: READ,
  },
  {
    slug: "instagram-messaging-api",
    term: "Instagram Messaging API",
    aka: ["Instagram API with Instagram Login"],
    channel: "Instagram",
    title: "What is the Instagram Messaging API?",
    definition:
      "The Instagram Messaging API lets approved apps send and receive Instagram direct messages for a professional account, under Meta's messaging rules.",
    detail: [
      // source: Instagram messaging API, read 2026-10-31: "enables your app users to send and receive messages"; from an Instagram professional account; permissions instagram_business_basic and instagram_business_manage_messages
      "Meta's docs say it lets an app's users send and receive messages from their Instagram professional account. With the newer Instagram Login, the account owner logs in with Instagram and grants permissions such as instagram_business_basic and instagram_business_manage_messages.",
      // source: same page: 24-hour window; human agent 7-day window; App Review page: Advanced Access needs App Review for apps that serve other businesses
      "The same rules apply to every app: replies within the 24-hour window, a 7-day window for people on your team with the human agent tag, and App Review before an app can serve businesses it doesn't own.",
      "Comments, private replies, story mentions, ice breakers and quick replies all build on it.",
      "There is an older way in too: the Instagram API with Facebook Login, which works through a Facebook Page linked to the Instagram account. The difference is how the account owner logs in and what they must set up first.",
    ],
    handling: [
      // source: platforms/instagram/oauth.py (instagram.com/oauth/authorize, BASE_SCOPES)
      {
        status: "yes",
        title: "Instagram Login",
        body: "You connect with your Instagram login. Amplychat asks for messages, comments and publishing; it doesn't need a Facebook Page.",
      },
      // source: settings.py ig_request_insights_scope default False (C-155)
      {
        status: "approval",
        title: "Post insights",
        body: "Post insights follow Meta's approval, so Amplychat doesn't ask for them yet.",
      },
      {
        status: "yes",
        title: "Instagram, WhatsApp and website chat in one inbox",
        body: "Instagram DMs and comments sit next to WhatsApp and website chat, with AI replies from your own knowledge.",
      },
    ],
    related: ["instagram-professional-account", "meta-app-review", "24-hour-messaging-window"],
    learn: { label: "The AI inbox", href: "/features/ai-inbox" },
    sources: [S.igMessaging, S.appReview],
    updated: READ,
  },
  {
    slug: "instagram-professional-account",
    term: "Instagram professional account",
    aka: ["Business account", "Creator account"],
    channel: "Instagram",
    title: "What is an Instagram professional account?",
    definition:
      "An Instagram professional account is a business or creator account, the account type Instagram requires for messaging tools and apps.",
    detail: [
      // source: Instagram Help "Set up a professional Instagram account", read through a search engine's copy on 2026-10-31 (the help centre blocks automated reads): switch a personal account to business or creator in settings; business suits retailers, local businesses, brands and service providers; creator suits public figures, content producers, artists and influencers; going professional makes a private account public
      "Instagram has two professional types. Instagram's help centre suggests a business account for shops, local businesses, brands and service providers, and a creator account for public figures, content producers, artists and influencers. You switch in the app's settings, and you can change the type later.",
      "A professional account is public: if your account is private, switching makes it public.",
      // source: Instagram messaging API, read 2026-10-31: messages are sent "from your Instagram professional account"
      "Meta's messaging API works only with professional accounts, so every DM tool needs one.",
      "Switching is done in the Instagram app and takes a few taps: you pick a category and the type. Going back to a personal account is possible too, though business tools stop working when you do. If you run an account for a shop or a service, business is the usual choice; if you publish your own work, creator. Both work the same way with messaging tools.",
    ],
    handling: [
      // source: platforms/instagram/oauth.py PROFESSIONAL_TYPES {BUSINESS, MEDIA_CREATOR}; services/connections.py ig_not_professional; lib/copy.ts
      {
        status: "yes",
        title: "Business and creator accounts connect",
        body: "Both types connect. A personal account is refused with a note on how to switch in the Instagram app.",
      },
      {
        status: "yes",
        title: "For businesses and creators",
        body: "The same inbox, AI replies and comment-to-DM work for both account types.",
      },
    ],
    related: ["instagram-messaging-api", "comment-to-dm", "meta-app-review"],
    learn: { label: "For businesses", href: "/for-businesses" },
    sources: [S.professionalAccount, S.igMessaging],
    updated: READ,
  },
  {
    slug: "meta-app-review",
    term: "App Review",
    aka: ["Meta App Review", "Advanced Access"],
    channel: "Meta",
    title: "What is Meta App Review?",
    definition:
      "App Review is Meta's check of an app before it can use permissions with Advanced Access, such as messaging, for accounts its developer doesn't own.",
    detail: [
      // source: Instagram Platform App Review, read 2026-10-31: "Your app must complete App Review before it can request permissions with Advanced Access from any app user"; a Tech Provider whose app serves multiple businesses needs Advanced Access; an app serving only a business you own or manage doesn't
      "Meta's docs say an app must complete App Review before it can request permissions with Advanced Access from any user. An app that serves many businesses needs that access; an app a business builds only for itself doesn't.",
      // source: Messenger message tags (read through a search engine's copy, 2026-10-31): the human agent tag needs approval
      "Some features need their own approval, such as the human agent tag. Until a permission is approved, Meta doesn't send the app those events or let it act for other accounts.",
      "This is why messaging tools say some features wait on Meta: the code can be ready before Meta has approved it.",
      "Review looks at how the app uses each permission, usually through a screen recording and written steps, and it can take more than one round. Until then, the app works only with accounts its developer owns or manages.",
    ],
    handling: [
      // source: app/(marketing)/ai-info/page.tsx and safety/page.tsx (App Review pending); gtm-pages.ts statuses
      {
        status: "approval",
        title: "Amplychat's review is in progress",
        body: "Instagram and WhatsApp connections depend on Meta's approval of Amplychat's app. Features that need it are marked With Meta's approval across the site.",
      },
      {
        status: "approval",
        title: "Facebook Pages and Messenger",
        body: "Built and waiting on Meta's approval, like Live comments, chats from ads and post insights.",
      },
    ],
    related: ["instagram-messaging-api", "human-agent-tag", "business-verification"],
    learn: { label: "Safety and Meta's limits", href: "/safety" },
    sources: [S.appReview, S.messageTags],
    updated: READ,
  },
  {
    slug: "human-hand-off",
    term: "Human hand-off",
    aka: ["Handover", "Conversation routing"],
    channel: "Meta",
    title: "What is human hand-off in chat automation?",
    definition:
      "Human hand-off is when an automated chat passes a conversation to a person on the business's team, so a human takes over the reply.",
    detail: [
      // source: Messenger Platform and Instagram Messaging API policy, read 2026-10-31: the example of a hybrid bot that "can also connect you to a customer service representative"
      "Meta's messaging policy gives the example of a hybrid experience, where automation answers simple questions and can also connect the customer to a person. Hand-off is what makes that work.",
      // source: Instagram Messaging changelog (read through a search engine's copy, 2026-10-31): the Handover Protocol is no longer supported for Instagram; businesses moved to Conversation Routing
      "When two apps share one account, for example a bot and a separate help desk, Meta passes the conversation between them. For Instagram, Meta has replaced its older Handover Protocol with Conversation Routing.",
      // source: Messenger message tags: the human agent tag is for a person answering
      "A person can take longer to answer than the 24-hour window allows; on Instagram and Messenger, the human agent tag gives them 7 days.",
      "A good hand-off is clear to the customer and to the team: the customer knows a person will answer, and the person sees the whole conversation so far.",
    ],
    handling: [
      // source: ai/policy.py (BUILTIN_ESCALATION_PHRASES, min_confidence), services/takeover.py; Meta's handover not used (platforms/facebook/webhooks.py)
      {
        status: "yes",
        title: "Needs you",
        body: "Refunds, complaints, legal threats, abuse, low confidence or your own phrases move a conversation to Needs you, inside Amplychat.",
      },
      {
        status: "yes",
        title: "Your reply pauses the AI",
        body: "When you reply yourself, the AI pauses for that conversation until you resume it or the time you chose passes.",
      },
      {
        status: "no",
        title: "Meta's conversation routing",
        body: "Amplychat is the one inbox, so it doesn't pass threads to another app.",
      },
    ],
    related: ["human-agent-tag", "24-hour-messaging-window", "instagram-messaging-api"],
    learn: { label: "The AI inbox", href: "/features/ai-inbox" },
    sources: [S.messengerPolicy, S.igChangelog, S.messageTags],
    updated: READ,
  },
];

export function glossaryPath(slug: string): string {
  return `${GLOSSARY_PATH}/${slug}`;
}

export function findTerm(slug: string): GlossaryTerm | undefined {
  return GLOSSARY.find((term) => term.slug === slug);
}

/** The letter a term files under: its first letter, or "#" for a number. */
export function termLetter(term: GlossaryTerm): string {
  const first = term.term.charAt(0).toUpperCase();
  return /[A-Z]/.test(first) ? first : "#";
}

/** The terms in A–Z order (numbers first), grouped by letter. */
export function glossaryByLetter(terms: readonly GlossaryTerm[] = GLOSSARY): { letter: string; terms: GlossaryTerm[] }[] {
  const sorted = [...terms].sort((a, b) => a.term.localeCompare(b.term, "en", { numeric: true }));
  const groups = new Map<string, GlossaryTerm[]>();
  for (const term of sorted) {
    const letter = termLetter(term);
    groups.set(letter, [...(groups.get(letter) ?? []), term]);
  }
  return [...groups].map(([letter, list]) => ({ letter, terms: list }));
}

/** The newest date a term's sources were read on. */
export function termChecked(term: GlossaryTerm): string {
  return term.sources.reduce((latest, source) => (source.checked > latest ? source.checked : latest), "");
}

/** The words a reader sees on the term page (the definition, detail and handling), for the length check. */
export function termWords(term: GlossaryTerm): number {
  const text = [term.definition, ...term.detail, ...term.handling.flatMap((item) => [item.title, item.body])].join(" ");
  return text.split(/\s+/).filter(Boolean).length;
}
