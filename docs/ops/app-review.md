# Meta App Review kit (GR-00)

For the owner, to get Social Hood through Meta's business verification and App Review in **one
submission** for Instagram and WhatsApp. The plan's section F lists the permissions;
this file has everything else.

Written 2026-10-23 from Meta's App Review submission guide and the Instagram Platform docs. Update
it at the end of every growth-plan wave. **Check Meta's current pages before submitting**; Meta
changes this process.

**Placeholders:**
- `<web>` is the production web domain, for example `app.socialhood.in`.
- `<api>` is the API domain.
- Replace both once production is deployed.

---

## 1. Before you can submit (owner track O-1 to O-4)

- [ ] **The business is registered** (O-1): sole proprietor, Udyam.
- [ ] **The public site matches the registration** (O-2). Each of these pages names the same legal
  name, address and contact email you give Meta:
  - [ ] `<web>/` (the footer);
  - [ ] `<web>/privacy`;
  - [ ] `<web>/terms`;
  - [ ] `<web>/data-deletion`.
- [ ] **Meta Business Portfolio verification is approved** (O-3). Advanced Access, which outside
  accounts need, requires it.
- [ ] **The permission list (section 3 below) is agreed** (O-4).
- [ ] **Production is deployed on its real domain over HTTPS**, and reviewers can sign up.

## 2. App settings to complete (Meta app dashboard)

| Setting | Value | Done |
|---|---|---|
| App icon | 1024 × 1024, our logo mark, no Meta logos | [ ] |
| App category | Business and pages (or the closest current option) | [ ] |
| App purpose | **Clients**: businesses that aren't ours connect their accounts | [ ] |
| Privacy policy URL | `<web>/privacy` | [ ] |
| Terms of service URL | `<web>/terms` | [ ] |
| User data deletion | Callback URL `<api>/webhooks/meta/data-deletion`. It answers Meta's `{url, confirmation_code}`, and the status page is `<web>/data-deletion` | [ ] |
| Deauthorize callback | `<api>/webhooks/meta/deauthorize` | [ ] |
| Instagram webhooks | Callback `<api>/webhooks/instagram`, with the verify token from `IG_WEBHOOK_VERIFY_TOKEN` | [ ] |
| WhatsApp webhooks | Callback `<api>/webhooks/whatsapp`, with the verify token from `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | [ ] |
| Instagram redirect URI | `<api>`'s Instagram OAuth callback (`IG_REDIRECT_URI`) | [ ] |
| Primary contact email | An inbox you read; review results go there | [ ] |
| Data handling questions | Answer them after business verification. We store tokens encrypted, messages for the plan's history period, and delete on request (`<web>/privacy`) | [ ] |

**Don't change basic or advanced settings while a review is open,** and **don't switch the app to
Live before approval.** Either can restart the review or limit you to the permissions already
approved.

## 3. The permissions and webhook fields

**One successful API call per permission within 30 days of submitting** is required. The request
button stays grey until Meta logs it, which takes up to 2 days. Make the calls from our app with a
role account: connect, receive and reply to a DM, reply to a comment, publish a post, read insights.

| Permission | Why we need it (draft use case; write it in your own words) | Test call that logs it | Screencast |
|---|---|---|---|
| `instagram_business_basic` | To connect a business's Instagram professional account to Social Hood and show its name, username and picture, so every message, comment and post in the app is tied to the right account. | Connect an account (reads `/me`) | S-1 |
| `instagram_business_manage_messages` | To show the business's Instagram DMs in one shared inbox and let its team reply. The AI suggests replies that a person approves (or answers automatically if the business turns Auto on). Automations send the link or offer someone asked for, only inside Instagram's 24-hour window. Conversation starters, entry links and click-to-DM ads open these conversations. | Receive a DM and reply from the inbox | S-2, S-3 |
| `instagram_business_manage_comments` | To show comments on the business's posts, Reels and Lives, with analysis of what people ask. The team can reply, hide spam or delete. Comment automations reply publicly and send one private reply to people who comment a keyword. | Reply to a comment; hide a comment | S-4 |
| `instagram_business_content_publish` | To publish the business's own images, carousels and Reels at the time they schedule in Social Hood's calendar. | Publish a test post | S-5 |
| `instagram_business_manage_insights` (only if `IG_REQUEST_INSIGHTS_SCOPE` is on) | To show the business how its posts and account perform (reach, views, interactions at 1 hour to 30 days), so it can compare posts. | Open a post's performance | S-6 |
| `whatsapp_business_messaging` | To show the business's WhatsApp chats in the same inbox and let its team reply. Outside the 24-hour window it sends only approved templates, and broadcasts go only to people who opted in. | Receive and reply to a WhatsApp message | S-7 |
| `whatsapp_business_management` | To connect the business's WhatsApp Business Account through Embedded Signup and read its phone number and approved templates. | Connect through Embedded Signup; open the template picker | S-8 |
| `business_management` (if Embedded Signup asks for it) | To complete Embedded Signup for the business's own portfolio. | Embedded Signup | S-8 |

**Webhook fields to subscribe** (app dashboard, Instagram product): `messages`, `messaging_seen`,
`message_reactions`, `message_edit`, `comments`, `messaging_postbacks`, `messaging_referral`,
`messaging_optins`, `live_comments`.
- They must match `SUBSCRIBED_FIELDS` in `apps/api/src/socialhood/platforms/instagram/adapter.py`.
- For outside accounts, webhooks arrive only with Advanced Access.

**Later submissions:** Facebook Pages (GR-29, section 8 below; GR-30 adds publishing and insights),
the WhatsApp catalogue (GR-33), and `ads_read` if GR-09 lists ads.

## 4. Screencast scripts

Meta's rules:
- one recording per permission, at 1080p or higher, with the screen width 1440 or less;
- English UI, no audio, a large cursor, mouse over keyboard;
- show **the permission being granted** and **the feature using it**.

Record on production with a test Instagram professional account that has a role on the app.

- **S-1 · Connect (basic):**
  1. Sign in to Social Hood.
  2. Open Settings › Connections and press Connect Instagram.
  3. Instagram's consent screen: grant the permissions.
  4. Back in Social Hood, the account card shows the name, username and picture.
- **S-2 · Inbox and reply (manage_messages):**
  1. From another phone, DM the test account.
  2. The Inbox shows the message live; open it.
  3. An AI draft appears: press Insert, edit it, press Send.
  4. Show the reply arriving on the phone.
- **S-3 · Automation and entry points (manage_messages):**
  1. Automations › New, from the "Send a link to commenters" template; save and activate.
  2. Show a DM keyword automation answering on the phone.
  3. Show an entry link (GR-08) and a conversation starter (GR-11) opening a conversation, once
     those are built.
- **S-4 · Comments (manage_comments):**
  1. Comment on a post from another account.
  2. Comments shows it with its analysis.
  3. Reply publicly; hide a spam comment.
  4. Show a comment automation sending its private reply.
- **S-5 · Publishing (content_publish):**
  1. Schedule › New post: add an image and a caption; publish now.
  2. Show it on Instagram.
- **S-6 · Insights (manage_insights):** open a published post's performance and the Home metrics.
- **S-7 · WhatsApp messaging:**
  1. Message the business number from a phone; it appears in the Inbox.
  2. Reply.
  3. After 24 hours, show that only a template can be sent.
- **S-8 · WhatsApp Embedded Signup (management):**
  1. Settings › Connections › Connect WhatsApp: complete Embedded Signup.
  2. The number appears.
  3. Open the template picker in a conversation.

## 5. Reviewer access

**What to give reviewers:**
- the production URL and how to sign up (email or Google through Clerk; no credit card on Free);
- the steps to reach each feature, matching the screencasts.

**What not to give them:** your personal Meta developer login. Reviewers use their own test
accounts.

**Test instructions for the submission (draft):**

> Sign up at `<web>` with any email. You land on Home. Go to Settings › Connections and connect
> your Instagram professional test account with Continue with Instagram. Then:
> - **Inbox:** send a DM to that account from another account. It appears in the Inbox, where you
>   can reply.
> - **Automations:** create one from a template and comment its keyword on a post.
> - **Comments:** comments on your posts appear there, where you can reply or hide them.
> - **Schedule:** publish a post from here.
>
> The app's UI is English.

## 6. Common rejections, and what to do about them

| Rejection | Our answer |
|---|---|
| A permission without a screencast | One recording per row in section 3; check the list before submitting |
| A recording that doesn't show the permission in use | Each script ends on the result: the reply on the phone, the post on Instagram |
| Generic or copied use-case text | Rewrite each draft in section 3 in your own words; no two the same |
| Reviewers can't reach the app | Sign-up must work on production; test it from a private window the day you submit |
| The icon or name conflicts with Meta's marks | Our own logo, no Instagram or WhatsApp glyphs in the icon |
| Allowed-usage rules not met | Keep the guardrails: replies only inside the window, one private reply per comment, no follow-gating, broadcasts only to opted-in contacts |

## 7. Timeline

| Step | How long |
|---|---|
| Business verification | Days to weeks, depending on documents |
| Logging the test API calls | Up to 2 days |
| App Review decision | About a week per round (Meta's guide); first submissions are often sent back once |

## 8. Second submission: Facebook Pages and Messenger (GR-29, O-10)

Send this after the first submission (Instagram and WhatsApp) is approved, from the same Meta app
and business. Everything in sections 1, 2 and 5 to 7 applies; this section adds what is different.
Every permission name and field below is **unverified until a real Page is connected**: check
Meta's current Messenger Platform and Pages API pages before submitting, and record what you find
in `docs/verification.md` item 36.

**Extra app settings** (Meta app dashboard):

| Setting | Value | Done |
|---|---|---|
| Facebook Login product | Add it; valid OAuth redirect URI `<api>/v1/oauth/facebook/callback` (`FB_REDIRECT_URI`) | [ ] |
| Webhooks product, **Page** object | Callback `<api>/webhooks/facebook`, verify token from `FB_WEBHOOK_VERIFY_TOKEN`; signed with the app secret (`META_APP_SECRET`) | [ ] |
| Server settings | `META_APP_ID`, `META_APP_SECRET`, `FB_REDIRECT_URI`, `FB_WEBHOOK_VERIFY_TOKEN` set on the API; without `FB_REDIRECT_URI` the Connect Facebook button answers "not configured" | [ ] |
| Human Agent | One request covers Instagram and Messenger; set `IG_HUMAN_AGENT_ENABLED` once Meta approves it | [ ] |

**Permissions** (Advanced Access; one successful call each within 30 days of submitting):

| Permission | Why we need it (draft; write it in your own words) | Test call that logs it | Screencast |
|---|---|---|---|
| `pages_show_list` | To list the Facebook Pages the person manages, so they pick which ones to connect to Social Hood. | Connect Facebook: the Pages list (`/me/accounts`) | S-9 |
| `pages_manage_metadata` | To subscribe the connected Page to message and comment webhooks, so the inbox and comments update as they arrive. | Connect a Page (`/{page}/subscribed_apps`) | S-9 |
| `pages_messaging` | To show the Page's Messenger conversations in the shared inbox and let its team reply. The AI suggests replies a person approves; automations send the link or offer someone asked for, inside Messenger's 24-hour window, and Human Agent replies up to 7 days. | Receive a Messenger message; reply from the inbox | S-10, S-11 |
| `pages_read_engagement` | To read the Page's posts and their comment and reaction counts, so each comment is shown on its post. | Open the Comments grid after connecting | S-12 |
| `pages_read_user_content` | To read the comments people leave on the Page's posts (*verify* whether `pages_read_engagement` covers this). | Open a post's comments | S-12 |
| `pages_manage_engagement` | To reply to comments as the Page, hide spam, delete comments, and send one private reply to a person who comments a keyword. | Reply to and hide a comment; automation private reply | S-12, S-13 |

Not requested yet (GR-30): `pages_manage_posts` and `read_insights` for publishing and best times.

**Webhook fields to subscribe** (Page object): `messages`, `message_echoes`, `messaging_postbacks`,
`messaging_referrals`, `message_reads`, `message_deliveries`, `message_reactions`, `message_edits`,
`messaging_optins`, `feed`.
- They must match `SUBSCRIBED_FIELDS` in `apps/api/src/socialhood/platforms/facebook/adapter.py`.
- Each Page is subscribed when it is connected, and again by the 6-hourly `reconcile_subscriptions`.

**Screencast scripts** (record on production with a test Facebook Page the reviewer account manages):

- **S-9 · Connect a Page (`pages_show_list`, `pages_manage_metadata`):**
  1. Settings › Connections › Connect Facebook; Facebook's consent screen: grant the permissions.
  2. Back in Social Hood, the list of Pages appears; tick the test Page and press Connect Page.
  3. The Page's card shows its name and "Facebook Pages API".
- **S-10 · Messenger inbox (`pages_messaging`):**
  1. From another Facebook account, message the Page in Messenger.
  2. The Inbox shows it live, with the Facebook mark; open it.
  3. Insert an AI draft or type a reply and press Send; show it arriving in Messenger.
- **S-11 · Automations on Messenger (`pages_messaging`):**
  1. Automations › New for the Page: a DM keyword automation; activate it.
  2. Send the keyword in Messenger; show the answer with its link button.
  3. Show an entry link (an `m.me` link with a `ref`) and a conversation starter opening a chat.
- **S-12 · Comments (`pages_read_engagement`, `pages_read_user_content`, `pages_manage_engagement`):**
  1. Comment on a Page post from another account.
  2. Comments shows it; reply publicly, hide a spam comment.
- **S-13 · Comment automation (`pages_manage_engagement`):**
  1. Create a comment keyword automation for the Page with a public reply and a private message.
  2. Comment the keyword; show the public reply under the comment and the private message in Messenger.

**Reviewer instructions (draft):**

> Sign up at `<web>`, go to Settings › Connections and press Connect Facebook. Continue as the test
> user, grant the permissions, tick the test Page and connect it. Then message the Page from
> another account (Inbox), and comment on its newest post (Comments). Automations can be created
> for the Page from the Automations tab. The app's UI is English.

**Guardrails to keep** (Meta's Messenger rules): replies only inside the 24-hour window (Human
Agent to 7 days once approved; no other message tags are used); one private reply per comment,
within 7 days; no follow gating (Messenger doesn't tell us who follows a Page, so there is no
follow message on Pages); nothing is sent to someone who hasn't written first.

## 9. Changelog

- 2026-10-23: first version (GR-00). Instagram fields include GR-01's four.
- 2026-10-25: section 8, the second submission for Facebook Pages and Messenger (GR-29).
