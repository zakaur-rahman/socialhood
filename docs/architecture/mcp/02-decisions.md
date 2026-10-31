# 02 · MCP server: decisions for the owner

- **Status:** approved 2026-10-31. The owner said "do your best" to all eight recommendations, so every decision below takes its recommended option.
- **Date:** 2026-10-31
- **Design:** [01-design.md](01-design.md)

---

## D1 · Who runs the sign-in (OAuth) for Claude and ChatGPT?

claude.ai and ChatGPT will only connect through OAuth: the user clicks Connect, signs in and approves. Something has to run that "approve" step and issue the tokens.

- **A. Clerk does it.** Clerk now supports what Claude and ChatGPT need: client registration, scopes and a consent screen.
  - **Good:** quickest start.
  - **Bad:** Clerk doesn't know our workspaces, so the user can't pick "Maple Bakery" on the consent screen. We'd add a second step inside the AI, and still build our own list of connections and the revoke button. Tokens last a day, and refresh tokens never expire. We can't change either.
- **B. Our own small sign-in server inside the Amplychat API, using the member's existing Clerk login.** *(recommended)*
  - **Good:** our consent screen shows the workspace picker, the plan, the member's role and plain-words permissions. Disconnecting in Settings works instantly. Tokens are short-lived.
  - **Bad:** about a week more work than A, and security-sensitive code that needs careful tests (planned).
- **C. A third-party service** (WorkOS, Stytch, Descope).
  - **Good:** it handles the OAuth details well.
  - **Bad:** a second identity system next to Clerk, a monthly bill, and the same workspace problem.

**Recommendation: B.** Also, ship API keys (`shk_`) as a second sign-in for Claude Code and Codex first, about a week earlier. They already exist.

**Trade-off:** about one extra week, in exchange for a clear consent screen, one workspace per connection, and instant revoke.

---

## D2 · Which plans get MCP?

Today the public API and Zapier are **Pro and Max only** (PD-6).

- **A. Pro and Max only, like the API.** Simple, but a Free user who finds us in Claude's directory hits "upgrade" before seeing anything.
- **B. Every plan. Free gets read-only plus drafts, with 100 calls a day; Pro and Max get everything, including scheduling.** *(recommended)* Free users see their inbox, comments and analytics inside Claude, and can save draft posts. "Schedule from Claude" is the reason to upgrade.
- **C. Every plan gets everything,** within each plan's existing post quota. The most generous, and the most abuse and cost risk (video storage).

**Recommendation: B**, as a new `ai_connections` entitlement, so it can change later without touching the API's PD-6.

**Trade-off:** a bigger funnel from the AI directories, against some free usage we pay for (capped).

---

## D3 · Should the AI's actions happen directly, or wait for approval in Amplychat?

- **A. Direct for posts, with safety nets.** *(recommended for R1)* Scheduling, changing and cancelling posts, uploading media, adding knowledge, and pausing or resuming automations happen at once. The safety nets:
  - Claude and ChatGPT ask the user to confirm;
  - posts can't be "publish now" (at least 5 minutes ahead);
  - owners and admins get a notification ("Claude scheduled a Reel for Fri 6 pm, by Asha") with a Cancel button;
  - every action is logged.

  **Sending DMs and comment replies isn't allowed in R1** (drafts only). In R2 sending comes, but only after a member approves it in Amplychat, using the existing approval system Ask uses.
- **B. Everything waits for approval in Amplychat.** Safest, but "schedule my Reel from Claude" becomes "go to Amplychat and click approve", which defeats the point.
- **C. Everything direct, including DMs.** Fastest. But a customer's DM could trick the AI into sending messages, and Meta's messaging rules make mistakes costly.

**Recommendation: A**, plus a Settings switch per workspace: off / read-only / drafts only / full. The default is full on Pro and Max.

**Trade-off:** a smooth experience for posts, while keeping customer-facing messages behind a human.

---

## D4 · How does the AI get a video or photo to us?

An AI can't paste a video into a tool call. The file has to travel another way.

- **A. Three routes, in R1:** *(recommended)*
  1. **Direct upload from the user's computer.** Claude Code and Codex run one upload command straight to our media store (Cloudinary). This is the "edit with Claude, post to Instagram" path.
  2. **Import from a link.** If the file is at a public link (Drive, Dropbox, or a link ChatGPT provides), we fetch it.
  3. **A drop page.** For claude.ai and ChatGPT, the AI gives the user a link to a small Amplychat page where they drop the file. It works on any device.

  In R2, add an upload button **inside** the Claude or ChatGPT chat (an "MCP App"), and ChatGPT's own file hand-off.
- **B. Only a link import.** Simplest, but users with a file on their computer are stuck.
- **C. Send files through our API server.** It works for everyone without Cloudinary credentials in the command. But 100 MB videos would go through our single server (1 GB memory), which we avoid today on purpose.

**Recommendation: A.** Also decide whether to switch on Cloudinary's paid malware-scan add-on for uploads. Recommended **off** for now: every image and video is re-encoded anyway. Turn it on if we want to say "scanned" in marketing.

**Trade-off:** a slightly clunkier flow on claude.ai (the drop page) until the R2 in-chat upload button, with no big files going through our server.

---

## D5 · TikTok: now, later or never?

- **The cost:** posting to TikTok is a new platform for us, needing TikTok's app approval and then an **audit**. Until the audit passes, every post is **private**. That's reported as taking weeks.
- **The rule that matters for AI:** for direct publishing, TikTok requires the creator to see a TikTok-specific confirm screen (privacy, comments, duet and stitch) before posting, so a purely AI "post it" flow won't pass review.
- **The easier mode:** "Upload to TikTok drafts", where the creator finishes the post in the TikTok app, has a lower bar.

- **A. Now, in R1.** Delays the whole MCP launch by 4–8+ weeks, with an uncertain audit.
- **B. Later (R3): start with "send to TikTok drafts", then direct posting with our own confirm screen.** *(recommended)* Launch MCP for Instagram first, measure demand, then build TikTok.
- **C. Never.** Keeps focus on Instagram, WhatsApp and the website, but loses the "Insta and TikTok" story competitors may tell.

**Recommendation: B.** Don't mention TikTok in MCP marketing until it ships.

**Trade-off:** a faster launch now, in exchange for no TikTok in the first release.

---

## D6 · Publish to the Claude and ChatGPT directories?

Without a listing, users add us by pasting our URL:

- in Claude, any plan can do that (Free: one custom connector);
- in ChatGPT, only Business, Enterprise and Edu workspaces with developer mode turned on can use our write tools.

- **A. Submit to both at launch.** *(recommended)* Needs:
  - a demo workspace with test Instagram accounts for reviewers;
  - a privacy policy section about AI connections;
  - support@amplychat.com as the contact;
  - for OpenAI, verifying the company in OpenAI's dashboard.

  Anthropic lists submissions as "Community" after an automated scan. OpenAI reviews them by hand.
- **B. Anthropic first, OpenAI after a month of real usage.** Less work at launch, but ChatGPT Plus users can't use us until then.
- **C. No directories. Docs page only.** Least work, and the least discovery.

**Recommendation: A.** Claude is ready on day one, and OpenAI's listing matters more for reach because of ChatGPT's plan limits.

**Trade-off:** about 2–3 days of listing, demo and policy work, plus review waiting, in exchange for being findable inside both apps.

---

## D7 · Where should the MCP server live?

- **A. Inside the existing API, at `https://api.amplychat.com/mcp`.** *(recommended)* No new server or container. It reuses all the existing rules and limits. It can be split out later without code changes.
- **B. A separate service at `mcp.amplychat.com`.** Isolated if MCP gets heavy, but another container on the one VM, and more to deploy.

**Recommendation: A.**

**Trade-off:** simplicity now. Heavy MCP use could slow the app's API, and we'd split it out if that happens.

---

## D8 · What does Free get from "Ask Amplychat" through MCP?

Ask Amplychat inside Claude or ChatGPT runs **our** AI (it costs us model credits) on top of **their** AI.

- **A. Same as in the app:** it uses the plan's existing AI credits. *(recommended)*
- **B. Leave Ask out of MCP.** The outside AI can already read our data with the other tools.
- **C. Pro and Max only.**

**Recommendation: A.** It's the one tool that gives cited, correctly calculated numbers, and the existing credit limits already bound the cost.

**Trade-off:** some double AI spend, bounded by the credits a plan already has.

---

### Smaller calls I'll make unless you say otherwise (recorded in CONFLICTS when built)

- Access tokens last 1 hour. Connections expire after 30 days unused (and after 180 days at most).
- One connection = one workspace. Connect again for another workspace.
- An AI-scheduled post must be at least 5 minutes ahead. "Publish now" waits for R2.
- AI uploads are capped per day: Free 20 files / 500 MB, Pro 200 / 10 GB, Max 1,000 / 50 GB.
- AI-created posts are capped per day: Pro 25, Max 100.
- The MCP audit log is kept 90 days.
