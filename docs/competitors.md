# Competitors

Written 2026-10-22, next to the detailed [Manychat comparison](competitor-manychat.md). Social Hood's
side is checked against the code (develop `0bcc67c`).

**How far to trust the competitor facts:**
- Their facts come from public pages read in October 2026. Most of those pages are comparisons
  **written by rival vendors**, and several tools' own pricing pages refuse automated reads.
- So treat every price as indicative, and check the vendor's site before quoting it.
- "Not found" means the research didn't confirm it either way.

## The four kinds of competitor

| Kind | Tools | What they're for | Where they beat us | Where we beat them |
|---|---|---|---|---|
| **Instagram DM automation** | Manychat, LinkDM, InstantDM, SuperProfile AutoDM, Inrō, CreatorFlow, ReplyKaro | Comment-to-DM funnels for creators and sellers | More triggers (stories, Live, ads, shares); lead capture; cheap entry plans | Publishing, comment intelligence, the WhatsApp inbox, AI with guardrails, analytics |
| **WhatsApp business platforms (India)** | Interakt, AiSensy, WATI | WhatsApp broadcasts, commerce and support | Broadcasts, catalogues and checkout, UPI and Razorpay payments, agent seats, chatbot builders | Instagram depth (comments, publishing), the AI's quality controls, analytics |
| **Omnichannel AI inbox** | Spur, respond.io | One AI agent across web chat, WhatsApp, Instagram, Messenger | More channels (web chat, Messenger, TikTok, voice); Shopify; AI that takes actions | Instagram publishing, comment intelligence, flat pricing (respond.io charges per contact) |
| **Social media suites** | Hootsuite, Metricool, Zoho Social | Publishing, analytics, a social inbox | Every network (Facebook, LinkedIn, TikTok, YouTube…); best times; competitor tracking and listening; reports | DM and comment automation, AI replies from knowledge, WhatsApp, lead scoring |

**What nobody else does:** combine all four. That means an Instagram and WhatsApp inbox, comment
automation, knowledge-based AI with escalation, comment intelligence, publishing and a
business-question assistant, at one price. Today a seller would buy one tool from each kind to get
this, for example Interakt plus Metricool, or Manychat plus Later.

## At a glance

✓ means yes, — means no, and *R2* or *R3* means planned in BUILD_SPEC §1.4. Prices are
third-party figures from 2026, per month.

| Tool | Channels | Comment and DM automation | Story triggers | AI on your knowledge | Contacts and broadcasts | Team inbox | Publishing | Commerce | Price |
|---|---|---|---|---|---|---|---|---|---|
| **Social Hood** | IG, WA | ✓ | *R2* | ✓, with escalation, gaps, Suggest and Auto | lead score only | inbox ✓, seats *R2* | ✓ IG | *R2* (catalogue, UPI) | set in Dodo (INR) |
| Manychat | IG, WA, Messenger, TikTok (beta), Telegram, SMS, email | ✓ visual flows | ✓ | add-on or Pro (sources conflict) | ✓ | ✓ | — | not re-checked | Pro $39 for 2,500 active contacts |
| LinkDM | IG, FB | ✓ (plus "Rewind" to earlier comments) | ✓ | — | email capture (Pro) | — | — | coupons | Pro $19 (25k DMs) |
| InstantDM | IG, FB | ✓ | ✓ | ✓ included | email capture | not found | — | Shopify | $9.99 flat (its own page) |
| SuperProfile | IG, Messenger | ✓ (Live too) | ✓ (Creator plan) | not found | leads (10 on Free) | not found | — | storefront, link in bio | Creator $29 per account |
| Inrō | IG | ✓ | not found | ✓ (FAQs, brand voice) | ✓ CRM, tags, segments, DM campaigns | not found | — | — | €12.99+, per contact |
| Interakt | WA, IG | ✓ on IG | not found | early (Haptik) | ✓ bulk campaigns | ✓ | — | ✓ catalogue, checkout, WhatsApp Pay | ₹999 (IG only) to ₹3,799, plus Meta fees |
| AiSensy | WA (IG not confirmed) | WA flows (₹2,500 add-on) | — | ✓ agent with knowledge base, from ₹3,500 | ✓ broadcasts | ✓ 5 agents included | — | ✓ Razorpay, UPI | ₹1,500 to ₹3,200, plus Meta fees |
| WATI | WA, IG, Messenger, TikTok (inbox) | ✓ chatbot flows | not found | paid add-on | ✓ | ✓ 5 users | — | not found | $59+, with a message markup |
| Spur | web chat, WA, IG, Messenger | ✓ (click-to-DM and click-to-WhatsApp ads) | not found | ✓ one agent on your knowledge, custom AI actions | not found | ✓ 2 to 10 seats | — | ✓ Shopify | $12 (IG) to $399 |
| respond.io | WA, IG, Messenger, TikTok and more, plus voice | ✓ workflows | not found | ✓ AI agents (Growth plan and up) | ✓ | ✓ | — | not found | $79 to $99+, per active contact |
| Hootsuite | all major networks | DM automations | not found | AI content assistant and smart replies | — | ✓ | ✓ | — | $99 per user |
| Metricool | all major networks | — | — | AI content assistant | — | ✓ inbox | ✓ (best times, competitors, ads) | — | ~$12 to $25 |
| Zoho Social | all major networks | — | — | not found | — | monitoring | ✓ (bulk, calendar) | — | $10 to $25 (annual) |

## The gaps that recur across competitors

These matter more than any single competitor's feature list. Each one shows up in several kinds of
tool.

| # | Gap | Who has it | Our status | Size |
|---|---|---|---|---|
| 1 | **Story reply and mention triggers** | Manychat, LinkDM, InstantDM, SuperProfile | *R2*; the webhooks already reach the inbox | S–M |
| 2 | **Lead capture and contacts:** ask for an email or phone in chat; a contacts list with tags, segments and export | Manychat, Inrō, LinkDM, InstantDM, SuperProfile, every WhatsApp platform | Missing (we have lead scores, but no list to act on); export is *R2* | M |
| 3 | **Team seats, assignment, saved replies** | WhatsApp platforms (5 agents included), Spur, respond.io, Hootsuite, Manychat | *R2*; the roles exist in the schema | M |
| 4 | **Broadcasts and campaigns** (WhatsApp templates to opted-in contacts) | Interakt, AiSensy, WATI, Manychat, Inrō | Missing; needs #2 and opt-in records | M |
| 5 | **Commerce:** a Shopify or product catalogue, checkout, UPI or Razorpay links | Interakt, AiSensy, Spur, InstantDM, Kanal | *R2* (catalogue, order capture, UPI) | L |
| 6 | **Ads and other ways in:** click-to-DM and click-to-WhatsApp ads, referral links and QR codes, ad and Live comments | Manychat, Spur, LinkDM, SuperProfile | Missing | S–M |
| 7 | **Integrations:** webhooks, Sheets, Zapier and Make, email tools (Kit, Flodesk) | Manychat, Inrō, Spur, LinkDM, AiSensy | Missing | M |
| 8 | **A website chat widget** using the same AI | Spur, respond.io, Tidio | Missing, not planned; cheap for us because the knowledge base and AI exist | M |
| 9 | **More publishing networks, best times, reports** | Hootsuite, Metricool, Zoho Social | Facebook is *R2* (roadmap P4); best times *R2*; LinkedIn *R3* | M–L |

## Where we're genuinely ahead, and where we're not

**Not unique any more:**
- An AI agent trained on a knowledge base: Spur, AiSensy, Inrō, InstantDM and respond.io all
  offer one.
- A shared inbox: every WhatsApp platform has one.
- Don't lead with either.

**What is distinctive** (for each, no competitor page we read showed it):
1. **The AI's quality controls:**
   - "Questions the AI couldn't answer";
   - escalation rules (refunds, legal action, complaints, abuse, low confidence, an answer not in
     your knowledge, your own phrases);
   - Suggest mode, where the AI drafts and a person sends;
   - takeover, which pauses the AI when you reply.
2. **Comment intelligence per post:** a summary, topics, sentiment, buying signals and spam, with a
   needs-reply count. DM tools only trigger on comments, and suites only list them.
3. **Inbox and publishing in one app.** Suites publish but barely automate; DM and WhatsApp tools
   automate but don't publish.
4. **Ask Social Hood:** answers to your own business questions, citing the figures it used.
5. **Following Meta's rules by design.**
   - InstantDM ("follow-gating") and SuperProfile ("follow gate") hold content back until someone
     follows. Our follow nudge never does: Meta's Spam Community Standard forbids requiring a
     follow for content (`services/automations/nudge.py`), and the editor says so.
   - Plenty of guides warn that Meta restricts accounts for automation abuse.
   - "Won't get your account restricted" is a real selling point.
6. **Flat pricing.** Manychat, respond.io and Inrō bill per active contact, and LinkDM and
   CreatorFlow per DM sent. We cap features, not audience, so a viral post doesn't cost more.

## Pricing context (India)

| Tool | Price per month |
|---|---|
| Instagram DM tools | ~$10 to $30 (₹850 to ₹2,500); ReplyKaro claims ₹99 |
| Interakt | Growth (both channels) about ₹2,500 to ₹2,800, plus Meta fees with a markup |
| AiSensy | ₹1,500 to ₹3,200, plus ₹2,500 for chatbots and ₹3,500 or more for the AI agent, plus Meta fees |
| Manychat | Pro $39 (about ₹3,300) for 2,500 contacts |

Our Pro price is set in Dodo, and the code doesn't fix it. To compete with Interakt Growth while
covering what a seller would otherwise buy as two tools, **₹1,500 to ₹2,500 a month** looks like the
right range. That's a judgement for you, not a finding.

## What to build, merged with the Manychat analysis

1. **Meta App Review** (roadmap P0). It still comes first.
2. **Story reply and mention triggers** (gap 1).
3. **Lead capture and contacts:** collect email or phone, a contacts list with tags, CSV export
   (gap 2).
4. **Ways in:** referral links and QR codes; click-to-DM and click-to-WhatsApp ads (gap 6).
5. **Team:** invites, assignment, saved replies (gap 3).
6. **WhatsApp broadcasts** to opted-in contacts (gap 4).
7. **Webhooks, then Sheets and Zapier** (gap 7).
8. **A website chat widget** with the same AI (gap 8). This is new and isn't on the roadmap yet.
9. **Commerce:** catalogue and UPI links (gap 5), then Facebook publishing and best times (gap 9).

**Skip for now:**
- social listening and competitor tracking (API limits);
- TikTok (gated beta everywhere);
- SMS (DLT rules in India);
- native mobile apps (the web app with push covers it).

## Sources

**Instagram DM tools:**
- [Kanal: LinkDM review and alternatives (prices as of 2026-10-11)](https://getkanal.com/blog/linkdm-review-pricing-alternatives)
- [InstantDM: Instagram DM tools compared (July 2026; vendor-written)](https://instantdm.com/blog/best-instagram-dm-automation-tools-2026-tested-and-compared)
- [SuperProfile: Manychat alternatives incl. India](https://superprofile.bio/compare/manychat-alternatives)
- [Inrō vs SuperProfile](https://www.inro.social/vs/superprofile)
- [InstantDM vs SuperProfile](https://instantdm.com/vs/superprofile)
- [Setsmart: Inrō review 2026](https://setsmart.io/blog/inro-review)
- [Inrō vs Manychat](https://www.inro.social/blog/blog-inro-vs-manychat-instagram)
- [Capterra: ReplyKaro](https://www.capterra.com/p/10048111/Replykaro/)

**WhatsApp platforms:**
- [Hyperleap: Interakt alternatives 2026](https://hyperleap.ai/comparison/best-interakt-alternatives-2026)
- [InstantDM vs Interakt](https://instantdm.com/vs/interakt)
- [respond.io: Interakt review](https://respond.io/blog/interakt-review)
- [AiSensy: pricing update from 1 July](https://wiki.aisensy.com/en/articles/11652273-pricing-update-effective-from-july-1)
- [QuickReply: AiSensy pricing 2026](https://www.quickreply.ai/blog/aisensy-pricing-plans)
- [Setsmart: AiSensy review](https://setsmart.io/blog/aisensy-review)
- [Capterra: WATI pricing](https://www.capterra.com/p/204314/WATI/pricing/)
- [Macha: WATI pricing explained](https://www.getmacha.com/blog/wati-pricing-explained)
- [Setsmart: WATI vs AiSensy](https://setsmart.io/blog/wati-vs-aisensy)

**Omnichannel AI inboxes:**
- [Spur vs WATI (Spur's page, May 2026)](https://www.spurnow.com/en/compare/wati-alternative)
- [Spur vs Interakt](https://www.spurnow.com/en/compare/interakt-alternative)
- [Spur vs respond.io](https://www.spurnow.com/en/compare/respondio-alternative)
- [eesel: respond.io pricing 2026](https://www.eesel.ai/blog/respond-io-pricing)
- [Macha: respond.io pricing explained](https://www.getmacha.com/blog/respond-io-pricing-explained)

**Social media suites:**
- [Capterra India: Zoho Social](https://www.capterra.in/software/159351/zoho-social)
- [Capterra: Metricool](https://capterra.com/p/203702/Metricool/)
- [SocialChamp: Metricool pricing](https://www.socialchamp.com/blog/metricool-pricing/)
- [Stork: Metricool](https://www.stork.ai/en/metricool)
- [NapoleonCat: Hootsuite pricing 2026](https://napoleoncat.com/blog/hootsuite-pricing/)
- [SocialPilot: Hootsuite pricing](https://www.socialpilot.co/blog/hootsuite-pricing)
- [Lakestar: Hootsuite](https://founders.lakestar.com/hootsuite/pricing)
