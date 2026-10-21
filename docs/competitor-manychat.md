# Social Hood vs Manychat

Written 2026-10-22. It checks ChatGPT's comparison against Manychat's public material and **our
actual code** (develop `0bcc67c`, the same as main).

**Sources:**
- Manychat's help centre and pricing page refuse automated reads (403). So Manychat facts come from
  third-party guides dated 2026, mostly October 2026.
- Facts that are long-standing but weren't re-checked this month are marked *(not re-checked)*.
  Check them on manychat.com before quoting them to anyone.

**Status words:**
- **Built:** in the code now.
- **Partial:** some of it is built.
- **Planned R2/R3:** in BUILD_SPEC's release plan (§1.4).
- **Missing:** neither built nor planned.

## 1. What Manychat has that we don't

### Channels

| Manychat | Us | Notes |
|---|---|---|
| Instagram, WhatsApp | **Built** | Our two channels |
| Facebook Messenger | Planned R2 | Roadmap P4 (Facebook Pages, Messenger, comments) |
| TikTok DMs | Missing | Open beta at Manychat; comment triggers mostly unavailable (TikTok-gated) |
| Telegram | Missing | Low value for our market |
| SMS | Missing | In India it needs DLT registration and costs per message |
| Email | Missing | Roadmap P6 (Outlook, then Gmail) |

### Automation triggers

| Manychat | Us |
|---|---|
| DM keywords | **Built** (word, exact and contains matching, with overlap warnings) |
| Post and Reel comments: one post, all posts, next post; keyword or any comment; public reply variations | **Built**, the same set |
| Story replies | Planned R2 (the inbox already receives them, but no automation can fire on one) |
| Story mentions | Planned R2 (same) |
| Instagram Live comments | Missing |
| Instagram ads (click-to-DM) | Missing |
| Referral links and QR codes (`ig.me/m/…?ref=`) | Missing |
| Share to DM (someone shares your post to their story) | Missing |
| Follow to DM (beta) | Missing (we have a "suggest following" nudge after a DM, not a trigger) |
| Ice breakers / conversation starters | Missing |

### The flow builder

| Manychat | Us |
|---|---|
| Visual drag-and-drop canvas | **Partial.** A step editor (When → On these posts → Keywords → Then → Settings) with preview, a test tab, runs and stats. One path, no canvas |
| Branching on button taps or conditions | Missing. "Tap first" is a single fixed two-step |
| Collect email or phone in the chat | Missing |
| Delays, randomizer and A/B split | **Partial.** Random public reply variations only |
| Multi-message sequences / drip | Planned R3 (follow-up sequences) |
| Actions: tag the contact, set a field, notify a teammate, call a webhook | Missing |

### Contacts (CRM)

| Manychat | Us |
|---|---|
| Contact list, tags, custom fields, segments | Missing. Conversations carry a lead score, intent and sentiment, but there is no contacts page, tag or field |
| Data export | Planned R2 |

### Broadcasts

| Manychat | Us |
|---|---|
| Broadcasts to segments (WhatsApp templates; Instagram within the 24 h window) | Missing. We have scheduled messages in one conversation and a WhatsApp template picker for replying outside the window |

### Team inbox

| Manychat | Us |
|---|---|
| Shared inbox | **Built** (a unified Instagram and WhatsApp inbox, real time) |
| Invite teammates, roles | Planned R2 (the schema has owner, admin and agent roles, but there's no invite flow) |
| Assign conversations, groups, per-agent limits | Planned R2 |
| Saved replies | Planned R2 |
| Native iOS and Android apps *(not re-checked)* | **Partial.** We have an installable web app with push notifications |

### Integrations and growth

| Manychat | Us |
|---|---|
| Zapier, Make, Google Sheets, HubSpot, Mailchimp, Klaviyo *(through Zapier or native; not re-checked)* | Missing |
| Public API and webhooks | Missing |
| Shopify and e-commerce, payments in chat *(not re-checked)* | Planned R2 (product catalogue, order capture, UPI requests) |
| Conversions API / ads tracking | Missing |
| Link click tracking in automations | Planned R2 |

## 2. What we have that Manychat doesn't

All of these are **built** today.

1. **Instagram publishing.** A composer for image, carousel and Reel posts, with AI captions,
   media library and crop. Also a calendar (week, month and list), a posting queue, posting times
   and hashtag groups. Manychat doesn't publish posts at all.
2. **Comment intelligence per post.**
   - Every comment is analysed: sentiment, question, buying signal or spam.
   - Each post gets an AI summary and topics, a needs-reply count and filter, and hide spam.
   - Reply, DM, hide or delete from one page, and the posts grid sorts by what needs a reply.
   - Manychat only triggers on comments; it doesn't help you understand them.
3. **AI that answers from your own knowledge, with guardrails.**
   - A knowledge base of documents and Q&A, a test box, and brand voice.
   - Per-account modes: Off, Suggest or Auto.
   - Escalation that always comes to you: refunds, legal action, complaints, abuse, low
     confidence, answers not in your knowledge, plus your own phrases.
   - Human takeover pauses the AI when you reply.
   - **"Questions the AI couldn't answer"** shows the gaps to fill.
   - In third-party reviews, Manychat's AI is a paid add-on that inserts generated replies into a
     scripted flow. There's no sign of knowledge-gap reporting or escalation rules.
4. **Message intelligence in the inbox.** Intent, sentiment, lead score and priority on every
   conversation; conversation summaries; AI drafts with Draft again and Insert; AI polish.
5. **A priority queue and follow-ups.**
   - Home shows the most urgent conversations first.
   - We remind you before the 24 h window closes on a lead scoring 60 or more.
   - A "Needs you" view lists the conversations handed back to you.
6. **Ask Social Hood.**
   - An assistant that answers questions about your posts, comments, conversations and automations.
   - It cites the figures it used and shows every step it took.
   - Manychat's AI talks to your customers; ours also answers your own questions.
7. **Analytics beyond automations.**
   - Home's metrics: needs reply, messages, the share handled by AI, median first response,
     sentiment, most commented posts and top intents.
   - Post performance read at 1 h, 6 h, 24 h, 72 h, 7 days and 30 days, compared with your earlier
     posts.
8. **Guardrails on automations.**
   - Cooldown per person, a run window, and an order when busy.
   - The 7-day comment limit handled, as "skipped (expired)".
   - A private-reply queue, and a disclosure line.
   - A dry-run test, and a preview with the first-name fallback.
   - Every run recorded with its reason.
   - Manychat leaves Meta's limits to you; its own docs warn that Meta may restrict accounts.
9. **India first.**
   - Pricing in INR, paid through Dodo. The Pro price is whatever the Dodo product is set to; the
     code never hard-codes one.
   - Hindi and Hinglish understood by the AI.
   - UPI payment requests planned (R2).
10. **Flat plans, not contact metering.**
    - Since 2 March 2026 Manychat bills by *active contacts*.
    - Its Free plan dropped to 25 contacts; Pro is $39 a month for 2,500, with overage per contact.
    - Our plans cap accounts, automations, AI credits and scheduled posts, never contacts. A
      viral post doesn't raise the bill.

## 3. Where ChatGPT's table was wrong about us

| ChatGPT said | Actually |
|---|---|
| "Basic comment automation described" | Comparable to Manychat's comment flows: post scope, three match modes, random public replies, tap first, link buttons, an image, the follow nudge, AI reply, cooldown and run window |
| AI replies from business knowledge "planned; parity not confirmed" | Built, with Suggest and Auto modes, escalation and knowledge gaps; arguably ahead |
| Automation insights "not confirmed" | Partial: each automation has Runs and Stats (runs, failures, a 7-day trend). Missing: link clicks and conversions |
| "Make cross-platform scheduling a core strength" | Publishing is Instagram only (WhatsApp has no publishing API; Facebook is R2). "Cross-platform" is a goal, not current |
| Audience intelligence "planned" | Built (analysis, summaries, comment intelligence) |
| Autonomous marketing agent | Ask Social Hood is built and read-only. Write actions are R2; autonomous mode is R3 |
| Manychat has TikTok | In open beta, with comment triggers mostly unavailable |

## 4. What I'd build, in order

**First: Meta App Review (roadmap P0).** Until it passes, no outside account can connect, so none
of the rest reaches customers.

Then the gaps that Instagram sellers expect from a Manychat replacement, cheapest and most-used
first:

| # | Gap | Size | Why now |
|---|---|---|---|
| 1 | **Story reply and story mention triggers** | S–M | Planned R2; the webhooks already arrive. Creators use them for giveaways and lead magnets |
| 2 | **Referral links and QR codes** (`ig.me` ref) plus a click-to-DM ads entry | S | A cheap way in from bios, websites and ads; no Meta review beyond messaging |
| 3 | **Contacts: a list, tags, CSV export** | M | Turns the lead scores we already compute into something a seller can act on; covers the R2 data export |
| 4 | **Branching and data capture in automations:** button choices to different messages, ask for an email or phone | M–L | The biggest functional gap. Do it as a structured branching editor, not a free canvas: easier to use on a phone and to test |
| 5 | **Team: invites, roles, assignment, saved replies** | M | Planned R2; the roles already exist in the schema |
| 6 | **Outbound webhooks, then Google Sheets and Zapier** | M | The "send my leads somewhere" request; webhooks first, apps on top |
| 7 | **Link click tracking** | S–M | Planned R2; gives automations a result beyond "sent" and feeds the Activity page (roadmap P1) |
| 8 | **WhatsApp broadcasts** to opted-in contacts with approved templates | M | Needs contacts (#3) and opt-in records; Meta charges per template message |
| 9 | Facebook Messenger and Pages | M–L | Roadmap P4 |

**Not worth chasing now:**
- **TikTok:** API-gated beta.
- **Telegram:** little use here.
- **SMS:** DLT rules and per-message cost in India.
- **Native mobile apps:** the web app with push covers it.
- **A free-form flow canvas:** branching (#4) covers the need.

## 5. Positioning

ChatGPT's main point holds: don't try to be a better Manychat, which already has the canvas, the
integrations and the brand.

Our angle, from what is built:

> **The AI inbox for Instagram and WhatsApp businesses.** It answers from your own knowledge, tells
> you what every comment and message means, publishes your posts, and costs a flat INR price,
> whatever goes viral.

Our proof points:
- the knowledge-grounded AI with escalation;
- comment intelligence;
- publishing;
- Ask Social Hood;
- flat pricing against Manychat's per-contact model.

Close gaps 1 to 4 above, and "switch from Manychat" becomes a credible message.

## Sources (Manychat)

- [Kanal: Manychat for Instagram (triggers, Meta rules, pricing as of 2026-10-11)](https://getkanal.com/blog/manychat-instagram)
- [Chatarmin: Manychat pricing 2026](https://chatarmin.com/en/blog/manychat-pricing)
- [Layer3 Labs: Manychat pricing 2026](https://www.layer3labs.io/guides/manychat-pricing)
- [DMChamp: Manychat pricing, contacts and AI costs](https://dmchamp.com/resources/manychat-pricing-2026/)
- [Manychat community: Share to DM trigger (2025-11-06)](https://community.manychat.com/product-updates/reward-followers-for-sharing-your-posts-to-their-stories-7643)
- [Manychat community: no DMs to new followers (Meta limits)](https://community.manychat.com/general-q-a-43/automatic-dm-to-new-instagram-followers-4583)
- [Guideflow: Manychat conversation assignment](https://www.guideflow.com/tutorial/how-to-add-an-assign-conversation-action-in-manychat)
- [Guideflow: assignment groups](https://www.guideflow.com/tutorial/how-to-allow-a-group-for-conversation-assignment-in-manychat)
- [Zapier: Manychat integrations](https://zapier.com/apps/manychat/integrations)
- [Setsmart: Manychat TikTok 2026](https://setsmart.io/blog/manychat-tiktok)
- [InstantDM: TikTok comment to DM 2026](https://instantdm.com/blog/tiktok-comment-to-dm)
- [Mooon AI: Manychat review](https://blog.mooonai.com/en/manychat)
