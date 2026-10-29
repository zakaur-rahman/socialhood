# 02 · Visual design recommendations

**Summary.** The paper-and-night system is calm, honest and already distinct from the gradient-and-badge WhatsApp tools. This doc keeps it and tightens it. It covers:
- fixing the two bugs;
- opening the hero on the sorted inbox, not the pile;
- shortening both scroll-scrubs;
- two heading tiers instead of one;
- a real spacing scale;
- restoring the paper/night alternation;
- using iris only where it means something.

Every copy change below is a **proposal** that reuses today's wording and positioning.

**The audit set:** [01 Current state](01-current-state-audit.md) · 02 Visual design (this file) · [03 Performance, accessibility and SEO](03-performance-accessibility-seo.md) · [04 Redesign proposal](04-redesign-proposal.md) · [05 Action plan](05-prioritized-action-plan.md) · [06 Design tokens](06-design-token-proposal.md)

Labels: **[Observed]**, **[Measured]**, **[Code]**, **[Hypothesis]**. Paths are relative to `apps/web/src/`.

---

## 1. Overall visual design

### What works [Observed]
- **A small system:** three grounds (paper #F5F5F2, sheet #FFFFFF, night #0F1017), one accent (iris #4B3FE0, or #A8A1FF on night), Geist 700 headings and 400/500 body. It reads as calm and grown-up.
- **Product scenes instead of stock art.** Every visual is the product's own UI vocabulary: notes, tags, a thread, a Reel, a DM. That is honest for a product with no customers yet.
- **Honest by design.** There are no badges, user counts or logo walls. Integration statuses say "waiting for Meta" where that's true. This follows the "don't copy" list.
- **Reduced motion is handled well.** Every scene renders complete and readable ([reduced-motion draft](shots/draft-reduced-motion-1440.png)).

### Major issues

| # | What | Where | Why it hurts | Fix | Benefit | Label |
|---|---|---|---|---|---|---|
| V1 | The AI draft becomes a white box with near-invisible words whenever motion is on | `site.css:280` `.typing` matches `.ddraft-t.typing` from `landing-motion.ts:247`. Shots: [1440](shots/draft-bug-1440.png), [375](shots/draft-bug-375.png) | It breaks the page's main proof ("AI replies from your own knowledge") for most visitors | Rename the DM dots class to `.dm-typing` (`site.css:280-283`, `landing-motion.ts:466`) | Restores the differentiator | Observed + Code |
| V2 | The H1 overflows its column and sits under the notes | `site.css:49, 133, 136`. [1440](shots/hero-1440.png) | The most important line is partly covered at the most common desktop sizes | See §5 (hero) | A clean first impression | Observed |
| V3 | Four paper sections in a row (Automations, Modes, Features, Integrations), about 4,700 px | `app/(marketing)/page.tsx` order. [Full page](shots/section-rhythm-1440-full.png) | The paper/night beat that defines the design disappears exactly mid-page; Features and Integrations look like one long list | Move Security up; merge Integrations into Features (§6) | The rhythm returns and the page gets shorter | Observed |
| V4 | Every H2 is 58 px/700; the closing H2 is 500 | `.h2` `site.css:51`; `.close h2` `site.css:391` | There's no hierarchy between story and utility sections, and the 500 closer looks like a different font choice | Two tiers (§3); closer at 700 | Clear reading order | Observed + Code |
| V5 | Ragged 3–4-line headings ("Everything / your customer / conversations need") | `.split-head` 1fr/1fr, `site.css:236` | It feels heavier and less minimal | `minmax(0,1.25fr) minmax(0,.75fr)` and `max-width: 18ch` | Two-line headings | Observed |
| V6 | Low-density frames: a 368 px inbox in a 620 px stage, about 290 px of blank paper under the hero facts at 1440, and an empty 470 px thread card at the start of How it works | `.inbox` `site.css:152`, `.thread-b` `site.css:205`. [Empty frame](shots/decide-empty-frame-1440.png) | The first frames look unfinished; at 1920 the scene is a postage stamp | Inbox `clamp(380px, 32vw, 480px)`; thread starts with the question; min-height 380 px | Fuller, more confident frames | Observed |
| V7 | "Every DM. Every comment." repeats in the stage caption (`Hero.tsx:104-107`), detached about 180 px below the inbox | Hero stage | Redundant decoration | Keep only "Example data" as a small label in the panel header | Less clutter; the honesty label stays | Observed |
| V8 | The Reel thumbnail is a grey box with a video icon | `Comments.tsx:56-59`. [Shot](shots/automations-1440.png) | The only "wireframe" moment on the page | A typographic Reel cover: night tile, caption in Geist 700, channel colour bar | Removes the template feel | Observed |
| V9 | Radii drift: 6, 9, 10, 12, 14, 16, 18, 20 and 22 px | `site.css` passim | It erodes the "precise" feel | Five steps (see 06) | Consistency | Code |
| V10 | The header is a grey slab over night bands (paper at 90% over #0F1017) | `.nav` `site.css:93-96`. [Draft shot, top](shots/draft-bug-1440.png) | Looks unfinished at band edges | Solid paper plus a 1 px rule and a soft shadow after scroll | Polished transitions | Observed |

---

## 2. Colour

### Assessment
- **The neutral ramp is disciplined** [Measured]: ink / ink-2 / ink-3 are 17.0 / 8.2 / 4.9:1 on paper, and night-ink / -2 / -3 are 17.0 / 9.6 / 6.0:1 on night.
- **Warm paper against cool iris is pleasant**, and the status colours are earthy.
- **Iris is overused** [Code + Observed]. It carries 11+ roles: kicker, H1 emphasis, links, focus, step numbers, feature icons, outgoing bubble, token, bar segment, FAQ hover and primary hover. It no longer marks either "act here" or "AI did this".
- **The secondary CTA is nearly invisible**: its border is 1.22:1. The primary CTA is ink, the same colour as the headings. That's fine for "minimal and bold", but the accent and the conversion point are disconnected.
- **Two pinks**: Instagram #BE185D and comment #E07FA8, the comment colour a tint of the Instagram one.
- **Three palettes on the public site**: the site's flat ink buttons, the app's indigo-gradient `ui/button` on data-deletion and unsubscribe (`--gradient-brand` isn't re-pointed in `.site`), and the old dark share image.

### Contrast failures [Measured with the WCAG 2.x formula; alpha shades composited over their real parent]

| Element | Colours | Ratio | Needs | Severity | Fix |
|---|---|---|---|---|---|
| AI draft text during the scene (the V1 bug) | #F2F2F5 on #EDEDE9 | ≈1.1 | 4.5 | **Critical** | Class rename |
| Secondary button border, paper | #DFDFDA on #F5F5F2 | 1.22 | 3.0 | Medium | #82848B → 3.42 |
| Secondary button border, night | ≈#414248 on #0F1017 | 1.90 | 3.0 | Medium | #6A6C76 → 3.63 |
| Knowledge lines dimmed to 50% while scanning | night-ink-2 at 50% on #181923 | 3.18 | 4.5 (14 px) | Medium | Opacity .72 (≈5.0) or night-ink-3 (5.52) |
| Knowledge lines dimmed to 35% ("miss") | night-ink-2 at 35% on #181923 | 2.22 | 4.5 | Medium | Opacity .6 (≈3.9). This is still under 4.5, so prefer night-ink-3 |
| Comment source dot | #E07FA8 on paper / sheet | 2.47 / 2.70 | 3.0 | Low (labelled) | Use #BE185D as a hollow 2 px ring |
| "Waiting" status dot | #D08A22 on paper | 2.62 | 3.0 | Low (labelled) | #B06A00 → 3.92 |
| Summary bar "other" segment | #B9B4F5 on sheet | 1.92 | 3.0 | Low (aria-hidden) | #8A82EB → 3.24 |
| Instagram dot on night | #BE185D on night-2 / night-3 | 2.89 / 2.52 | 3.0 | Low | #E0559A → 4.94 / 4.29 |
| Web dot on night | #0F766E on night-3 | 2.78 | 3.0 | Low | #2AA597 → 5.01 |
| `brand-strong` fill inside `.night` (latent; inner pages) | #4B3FE0 on night | 2.79 | 3.0 | Low | Re-point to iris-night |
| Near-misses (they pass, but only just) | ink-3 on paper-2 / iris-soft | 4.54 / 4.50 | 4.5 | Low | ink-3 → #5E616A (5.27 / 5.23) |

All other text pairs pass AA with margin. The full table is in the research and condensed in [06](06-design-token-proposal.md).

### Recommendation
- **Keep paper, ink, night and iris.** Add a control-border token, and nudge ink-3 darker.
- **Accent discipline.** Iris is for links, focus, selected states, the primary hover and AI moments (drafts, citations, "One inbox."). Move kickers, `.steps .n` numbers and feature icons to ink or ink-3.
- **Primary CTA:** stay ink with white text (18.56:1). Change its hover from iris #4B3FE0 to iris-ink #3A2FC2 (8.88:1 with white), so it reads as a press rather than a colour swap.
- **Channel colours as the brand motif:** see [04](04-redesign-proposal.md). Scale them up as 3 px bars rather than 8 px squares.

---

## 3. Typography

**Keep Geist.** It renders cleanly at 700 with tight tracking, it is a single variable file and it has a metrics fallback.

What's wrong [Observed + Code]:
- 16 rendered sizes, 16 line-heights and 12 letter-spacings, with no type tokens.
- H2 is 58 px against an 81 px H1 (a ratio of 0.72–0.85: too flat).
- 11 px text (`.pro`, `.pl`, avatar letters).
- The closing H2 is 500.

### Current vs proposed scale
The fluid formula runs from 390 px (mobile) to 1440 px (desktop): `min + (max − min) × (100vw − 390px) / 1050px`. The values were checked by hand.

| Role | Current | Proposed token | Proposed `clamp()` | 390 → 1440 | Weight / LH / tracking |
|---|---|---|---|---|---|
| Landing H1 | `clamp(46px, 5.6vw, 82px)` | `--type-display` | `clamp(2.75rem, 2.193rem + 2.286vw, 4.25rem)` | 44 → 68 | 700 / 1.0 / −0.045em |
| Inner page H1 | `clamp(38px, 5vw, 66px)` | `--type-h1-page` | `clamp(2.25rem, 1.693rem + 2.286vw, 3.75rem)` | 36 → 60 | 700 / 1.04 / −0.04em |
| H2, story sections + closer | `clamp(34px, 4.2vw, 58px)`; closer `clamp(38px, 4.8vw, 66px)` at **500** | `--type-h2` | `clamp(2rem, 1.536rem + 1.905vw, 3.25rem)` | 32 → 52 | **700** / 1.06 / −0.035em |
| H2, utility sections (Integrations, FAQ, Security if wanted) | same 58 px | `--type-h2-sm` | `clamp(1.75rem, 1.471rem + 1.143vw, 2.5rem)` | 28 → 40 | 700 / 1.08 / −0.03em |
| Band title | `clamp(26px, 3vw, 36px)` | `--type-h3` | `clamp(1.5rem, 1.314rem + .762vw, 2rem)` | 24 → 32 | 700 / 1.12 / −0.025em |
| Card title | 20 / 22 px, 4 trackings | `--type-title` | `1.25rem` (plans may keep 22 px) | 20 | 600 / 1.25 / −0.015em |
| Stat (price, strip values) | 64 / 52 / 40 / 28 / 26 / 20 | `--type-stat` | `clamp(2.75rem, 2.286rem + 1.905vw, 4rem)` | 44 → 64 | 700 / 1.0 / −0.04em |
| Strip value | 20 px | `--type-stat-sm` | `clamp(1.5rem, 1.314rem + .762vw, 2rem)` | 24 → 32 | 700, `tabular-nums` |
| Lede, hero sub | 18 / 19 px | `--type-lede` | `clamp(1.0625rem, 1.016rem + .19vw, 1.1875rem)` | 17 → 19 | 400 / 1.55 |
| Body | 16 px, LH 1.6 / 1.7 | `--type-body` | `1rem` | 16 | 400 / 1.6 |
| Small body, buttons | 15 px | `--type-body-sm` | `.9375rem` | 15 | 400 (buttons 600) / 1.55 |
| Label (kicker, facts, footer) | 14 px | `--type-label` | `.875rem` | 14 | 400; kicker 500, +0.01em |
| Caption | 13 px | `--type-caption` | `.8125rem` | 13 | 400 / 1.45 |
| Micro (tags, chips) | 12 px and **11 px** | `--type-micro` | `.75rem`, the minimum | 12 | 600 / 1.35 |

**Why 68 px for the H1.** "Every comment." measures about 7.15 × the font size in Geist 700 at −0.05em. That is 576 px at 80.6 px [Measured], so 68 px gives about 486 px. With a 1fr/1fr hero grid the copy column is about 564 px at 1440 and about 474 px at 1061, where the H1 is about 59 px (about 424 px). It fits at every desktop width. [Hypothesis: re-check 901–1000 px, where the margin is under 10 px.]

**Other rules:**
- Keep `text-wrap: balance` on headings and `pretty` on ledes.
- Add `max-width: 18ch` to H2s and `14ch` to the closer.
- Add a comment at `globals.css:455` exempting `.site` from the 400/500/600 rule (C-155), so a lint pass doesn't undo the bold headings.

---

## 4. Header and navigation [Observed]

Today: 65 px tall, sticky, a 90% paper veil with 14 px blur, no change on scroll. There are 5 links, Sign in (ghost) and Start free (ink, 99×40). Below 900 px it shows the logo, Start free and a 44×44 menu button.

| Finding | Severity | Fix |
|---|---|---|
| Header CTAs are 40 px tall; on phones "Start free" is a primary touch target | Medium | `.nav .btn { min-height: 44px }` at ≤900 px |
| No scrolled state; grey slab over night bands (V10) | Low | Solid `var(--paper)`, plus `box-shadow: 0 1px 0 var(--rule-2), 0 8px 24px -16px rgb(18 19 23 / .18)` after 8 px of scroll, toggled by one IntersectionObserver sentinel |
| Mobile menu: an outside tap doesn't close it, Tab leaves the open panel, no scrim, the page scrolls under it ([shot](shots/mobile-menu-375.png)) | Medium | Close on outside `pointerdown` and on `focusout` from the panel; a scrim `rgb(15 16 23 / .24)` |
| Three "Start free" buttons at once when the menu is open on a phone | Low | Remove "Start free" from the menu actions (keep Sign in) |
| Menu action buttons are 40 px | Low | 48 px, matching the hero |
| 768 px uses the phone header; the 5 links (384 px) would fit | Low | Move the header breakpoint to 760 px, with a 20 px link gap at 761–1060 |
| CTA hierarchy is right (one ink button, Sign in as ghost) | — | Keep |

---

## 5. Hero deep-dive

### Assessment
- **Message (5-second test)** [Hypothesis on Observed copy]:
  - *What it is* is clear: "Every DM. Every comment. One inbox." plus the sub-line.
  - *For whom* is only implied. "Small businesses and creators" never appears in the hero.
  - *The differentiator* (AI that knows your business, and hands off the tricky ones) is in the 19 px sub-line. The headline itself is category-generic.
- **Layout** [Observed]:
  - Desktop is two columns (0.9fr / 1.1fr, gap 48), with a 508 px copy column and a 620 px stage.
  - It is a **250vh scrub**: 2,250 px at 1440. The sticky frame fills the viewport, so nothing else shows for about 1,400 px of scrolling.
  - The first frame is the scattered pile, with one card touching the nav at 1366.
- **Conversion** [Observed]:
  - The primary CTA is above the fold at all six widths. Its bottom edge sits at 584 / 768 (1366), 656 / 900 (1440), 748 / 1080 (1920), 539 / 812 (375), 509 / 932 (430) and 445 / 1024 (768).
  - The CTA hierarchy is correct: ink "Start free →" 141×48, outlined "See how it works" 168×48.
  - The trust facts are 14 px #686B74, which is present but quiet.

Screenshots: [1440](shots/hero-1440.png) · [1920, sorted end state](shots/hero-1920-sorted.png) · [768](shots/hero-768.png) · [375](shots/hero-375.png)

### The five problems
| # | Problem | Severity | Confidence | Effort |
|---|---|---|---|---|
| 1 | **The first frame shows chaos, not the product.** The pile says "messages are a mess" while the H1 promises the fix, so the image and the headline contradict each other | High | Medium | M |
| 2 | **The 250vh scrub delays everything.** 1.5 viewports for one transform. A fast scroller sees a sticky hero that "doesn't move" | High | Medium | M |
| 3 | **The H1 overflows its column and sits under the notes** (V2) | High | High | S |
| 4 | **The differentiator and the audience are buried** in the sub-line or absent | Medium | Medium | S |
| 5 | **Weak scale relationship.** An 80 px headline beside a 368 px card makes the product look small; at 1920 the card floats in a 1016 px frame | Medium | High | S |

### Layout strategy
- **Lead with the sorted inbox, the promise.** The pile can still appear for a moment as the "before" in a one-shot entrance (≤1.2 s, transforms only, `cubic-bezier(.2,.7,.2,1)`), or not at all.
- **Remove the scrub, or cut it to ≤140vh** and start it at the halfway point. This is an owner question (see [05](05-prioritized-action-plan.md#questions-for-the-owner)).
- **Make the hero one viewport:** `min-height: min(100svh - 64px, 860px)`. Let the top 24–40 px of the Strip show at 1366×768 as the scroll cue, and remove the "Scroll to sort the inbox" text.
- **Put the copy above the scene:** `.hero-copy { position: relative; z-index: 2 }`, so a note can never cover text.

### Type and colour
- H1: `--type-display` (44 → 68 px), 700, LH 1.0, −0.045em. Keep "One inbox." in iris; it is an AI/product moment, which fits the accent rule.
- Sub-line: `--type-lede`, `max-width: 44ch`, #464953.
- Trust row: raise from ink-3 to ink-2 #464953 (8.22:1).
- Scene: channel colour as a 3 px left bar on each note instead of the 8 px square; panel chips "2 need you" (wait tones) and "3 AI drafts" (iris-soft).

### Copy proposals
These are **proposals**. Each keeps today's wording and positioning; anything new is marked for a fact-check.

| ID | Where | Today | Proposal | Fact-check |
|---|---|---|---|---|
| H-1 | Eyebrow (it orphans "WhatsApp" at 375 and 430) | "AI inbox and automations for Instagram and WhatsApp" (`SITE_TAGLINE`) | "AI inbox for Instagram and WhatsApp" (`SITE_TITLE_LINE`, `site.ts:70`: existing words) | None. Website chat is missing from both lines; see [03](03-performance-accessibility-seo.md) SEO content |
| H-2 | Sub-line | "AI that knows your business drafts or sends the reply on Instagram, WhatsApp and your website, and hands the tricky ones to you." | "For small businesses and creators: AI that knows your business drafts or sends the reply on Instagram, WhatsApp and your website, and hands the tricky ones to you." | **Confirm** the audience phrase. It comes from the product brief and the meta description ("for businesses and creators"), not the hero today |
| H-3 | H1 | "Every DM. Every comment. One inbox." | **Keep as is.** Make the differentiator visible through the panel chips "AI draft" / "Needs you" (already in the scene) | None |
| H-4 | Trust row | "Official Meta APIs · Free plan, no card needed" | Add "No password asked" (wording from the closer: "Official Meta APIs, no password asked") | **Confirm** it's still accurate for every channel |
| H-5 | Secondary CTA | "See how it works" | Keep. On phones, a text link under a full-width "Start free" | None |
| H-6 | Stage caption | "Every DM. Every comment." → "One inbox. Example data." | Only "Example data", as a label in the panel header | None |

### Desktop, tablet and mobile layouts
| | Desktop (≥1061 px) | Tablet (601–1060 px) | Mobile (≤600 px) |
|---|---|---|---|
| Grid | `minmax(0,1fr) minmax(0,1fr)`, gap `clamp(40px, 4vw, 80px)`; copy `max-width: 600px` | One column (≤900) or 1fr/1fr (901–1060, as today) | One column |
| H1 | 59 → 68 px (`--type-display`) | ≈49–59 px (the same token; no longer stuck at 46) | 44 px, 3 lines |
| Scene | Sorted inbox `width: clamp(380px, 32vw, 480px)`, vertically centred | Inbox 440 px wide, **left-aligned to the text edge** | Full width; play the sort **once** when in view, then hold (no 9 s loop) |
| CTAs | Inline, 48 px | Inline, 48 px | "Start free" full width, 48 px; "See how it works" as a text link below. This saves about 60 px and lifts the inbox top above the fold on 812 px phones [Hypothesis on the exact gain] |
| Height | `min(100svh - 64px, 860px)`; no sticky (or ≤140vh) | Content height | Content height |
| Extra | Strip edge visible as the scroll cue | — | Eyebrow H-1; `.panel-h .num { white-space: nowrap }`, so "8 conversations" doesn't wrap |

### Animations: keep, simplify or remove
| Motion | Verdict | Why |
|---|---|---|
| Pile → inbox scrub (250vh) | **Simplify:** sorted at load plus a one-shot ≤1.2 s sort, or a ≤140vh scrub | Costs 1.5 viewports and opens on the wrong frame |
| Idle bob on the notes (`site-bob`, infinite) | **Remove** | Moves beside text and means nothing; it also blocks WCAG 2.2.2 |
| Phone 9 s sort / hold / unsort loop | **Simplify** to one sort on view | An endless loop competes with the CTA, and un-sorting undoes the promise |
| Tag fade-in after sorting | **Keep** | It shows the AI's triage |
| "Scroll to sort the inbox" hint | **Remove** | Instruction text; the Strip edge is the cue |

---

## 6. Section by section (actual order)

| # | Section | Verdict | What to change |
|---|---|---|---|
| 1 | Hero | **Improve** | §5 |
| 2 | Strip | **Improve, move up** | Values at `--type-stat-sm` (24–32 px, 700, tabular numbers), labels 14 px. On desktop make it the hero's bottom edge (the scroll cue). Replace the duplicated "Official Meta APIs" (it appears in the hero, Trust and the closer) with another true fact. One candidate is "Website chat on every plan", from the Integrations status; **fact-check** it |
| 3 | How it works (night) | **Improve, high priority**: the strongest asset | Fix V1. Scrub 340vh → about 200vh. A compact title row (kicker + H2 at `--type-h2-sm`) **inside** the sticky frame. Start with the customer's question already in the thread. `.thread-b { min-height: 380px }` (wide) / `auto` (≤900). Step labels sit near the bottom edge (y ≈ 760–810 of 900); lift them. Rename the kicker or merge the setup steps here, so there aren't two "how" sections |
| 4 | Automations | **Improve** | Typographic Reel cover (V8). Keyword field: iris 1.5 px border at rest and the label "Try your own keyword" (proposal; today "The keyword is yours"). Fold the comment summary bar into the Features "Comment intelligence" item. At ≤900 show Reel → DM, with the rule as a 4-step list (the section is 2,192 px at 375). The "DMs sent 28" stat is cut by the fold at 1440 ([shot](shots/automations-1440.png)) |
| 5 | Modes + setup | **Improve and split** | Kicker "AI reply modes" (proposal; today "Set up in three steps", which mismatches the H2). Move the three setup steps out into a short numbered band before Pricing. On phones hide the "Tagged as" column |
| 6 | Features | **Improve and merge** | Nine identical items with iris line icons is the most template-like section ([shot](shots/features-1440.png)). Group into three labelled clusters: *Publish* (scheduling); *Understand* (comment intelligence, analytics, Ask Amplychat); *Sell and scale* (catalogue, sequences, team, notifications). Give **Ask Amplychat** a larger card (the second AI differentiator). Drop "Chat widget" (Integrations covers it). Link items to `/features/*` |
| 7 | Integrations | **Merge** into Features as a final "Connections" block | A dense grid of `name · status` chips, with the descriptions behind a disclosure. Remove `style={{ paddingTop: 40 }}` (`Channels.tsx:85`). Keep the status dots: they are exactly the right honest pattern |
| 8 | Security (night) | **Keep, move up** to after Modes | Restores the paper/night beat and answers "is this safe for my account?" earlier. H2 `max-width: 16ch` ("messages," sits alone today). Lead with the items not said elsewhere (encrypted tokens, workspace separation, deletion in 24 h). Add a link to `/security` |
| 9 | Pricing | **Keep, improve** | Show the 5 most decisive limits and collapse the rest. Free is already primary when Pro isn't on sale (`Pricing.tsx:137`). The "Compare every plan limit" link is 19 px tall; make it 44 px |
| 10 | FAQ | **Improve: trim** | 15 → 6–8 that answer purchase objections (ban risk, password, Professional account, robotic replies, taking over, free limit), plus a link to all questions. Heading column `minmax(0,.7fr)` and `--type-h2-sm`, so "Common questions" stays on one line |
| 11 | Closing CTA (night) | **Keep, improve** | H2 at 700, `max-width: 14ch` (4 lines at 1440 today). Two CTAs ("Start free", "See pricing"); the support email becomes a plain line "Questions? support@amplychat.com" |
| – | Footer | **Keep** | Night, five columns, an honest "not affiliated with Meta" line ([shot](shots/footer-1440.png)). The "Legal and trust" column is 10 links, twice the height of the others; consider two columns. Footer links 32 px → 44 px on touch. Column titles as non-heading text (see 03) |

New, only where a real need exists:
- **"Who it's for"**: two cards linking to `/for-creators` and `/for-businesses` (both pages exist). This answers "is this for me?" without testimonials.
- **A liveness line**: "What's new" linking to the changelog, which is already in the footer.

---

## 7. Layout and spacing

### Today [Observed + Code]
- Container: `.wrap` `max-width: 1240px`, gutters 32 px (≥901) and 16 px (≤900). That leaves 340 px of margin each side at 1920 and about 660 px at 2560 ([shot](shots/wide-2560.png)). This is allowed: C-074 keeps the marketing site centred.
- Section padding: 136 px (≥901) / 88 px (≤900). That puts **272 px** of empty paper between same-colour bands.
- Heading-to-content gaps: 64, 56, 40 and 72 px; nine bespoke values in all. Grid ratios are bespoke per section.
- Hidden overflow: `.site { overflow-x: clip }` hides real overflow (the V1 box at 375, the H1 phrase). Hero notes are z-index 3, above the H1, which has none.
- Sticky frames use `100vh`. On iOS Safari, `100svh` avoids a frame taller than the visible area [Hypothesis; not testable in Chromium].

### Proposed values
These map to the tokens in [06](06-design-token-proposal.md).

```css
.site {
  --space-section: clamp(72px, 6vw + 40px, 128px);        /* 72 @375 → 126 @1440 → 128 cap */
  --space-section-tight: clamp(48px, 4vw + 24px, 88px);   /* between two same-colour bands */
  --space-head: clamp(32px, 2.5vw + 16px, 56px);          /* heading block → content */
  --gutter: clamp(16px, 3vw + 4px, 64px);                 /* 16 @375, 27 @768, 47 @1440, 62 @1920 */
}
.site .wrap { max-width: calc(var(--container-site) + 2 * var(--gutter)); padding-inline: max(var(--gutter), env(safe-area-inset-left)); }
.site .sec { padding-block: var(--space-section); }
.site .sec:not(.night) + .sec:not(.night) { padding-top: var(--space-section-tight); }
.site .split-head { grid-template-columns: minmax(0, 1.25fr) minmax(0, .75fr); gap: 48px; }
.site .split-head + * { margin-top: var(--space-head); }
.site .hero-grid { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: clamp(40px, 4vw, 80px); }
.site .hero-copy { position: relative; z-index: 2; }
.site .inbox { width: clamp(380px, 32vw, 480px); }
.site .thread-b { min-height: 380px; }
@media (max-width: 900px) { .site .thread-b { min-height: 0; } }
```

The adjacent-band selector is a sketch; the paper-2 bands (Modes, FAQ) count as a colour change. Remove `style={{ paddingTop: 40 }}` from `Channels.tsx:85`. `--container-site` stays 1240 px unless the owner chooses wider (see the questions in 05).

---

## 8. Components and interactions

| Component | Observed state | Issue | Fix |
|---|---|---|---|
| Primary `.btn-main` | 48 px, r12, 15 px/600, ink; hover → iris; arrow nudges 3 px; focus 2 px iris, offset 3 | The hover is a big hue jump | Hover #3A2FC2, 150 ms |
| Secondary `.btn-line` | 48 px, 1 px #DFDFDA | 1.22:1 border | #82848B (3.42:1); hover border ink, bg ink at 5% |
| Ghost email button (closer) | 48 px button | Competes with two real CTAs | A text line |
| Nav buttons | 40 px | <44 px on touch | 44 px at ≤900 |
| Small links | "Compare every plan limit" 19 px tall, "Privacy Policy" 23 px | Below the 24 px WCAG 2.5.8 minimum | `padding-block: 10px; margin-block: -10px` |
| Tags | 22 px, r6, 12 px; Pro badge 11 px | 11 px text | 12 px minimum |
| Keyword input | 44 px, r10, ink-3 border, iris focus | Looks static at rest | Iris 1.5 px border at rest plus the proposed label |
| Mode switch | 3 × 44 px, `aria-pressed`, live description | Accessible name "AutoPro" | `<span class="pro" aria-label=", Pro plan">` or a visually hidden separator |
| FAQ | `<details>`, 69 px rows, + rotates | 15 items | Trim |
| Cards | r18–22, 1 px rule, sheet | Radius drift | Radius scale |
| Shadows | Only `--shadow-panel` and `--shadow-note` | Good restraint | Keep |
| Footer links | 32 px (desktop), 40 px (≤900) | <44 px on touch | 44 px at ≤900 |

**Motion rule:** every loop runs once, or stops when off screen or after about 5 s, and nothing moves next to body text.
- *Purposeful (keep):* citations → wires, the keyword-driven comments and the mode swap.
- *Distracting (cut):* the infinite bob, the closer's falling rows, the un-sorting phone loop, and the comment stream while the visitor reads.

---

## 9. Responsive findings by viewport [Observed]

| Viewport | Findings | Fix |
|---|---|---|
| **375×812** ([hero](shots/hero-375.png)) | No horizontal scroll. H1 46 px, 3 lines (good). The eyebrow orphans "WhatsApp". The CTA bottom is at 539. The inbox header wraps "8 / conversations". V1 is worst here (the box overflows to x=381; [shot](shots/draft-bug-375.png)). A 470 px empty thread void. The header CTA is 40 px. The page is 20,278 px (Features 2,099, Pricing 2,705, FAQ 1,962). The closer is 4 lines at 500 | Fix V1; H-1 eyebrow; `nowrap` on the panel count; 44 px nav CTA; trim the FAQ; group Features |
| **430×932** | As 375; the eyebrow still wraps; the CTA bottom is at 509 | Same |
| **768×1024** ([hero](shots/hero-768.png)) | Phone layout (the breakpoint is 900). **H1 stuck at 46 px** in a 736 px column. The inbox is centred with 184 px of empty space each side, misaligned with the left-aligned copy. Notes caught overlapping the panel edge mid-loop. H2 34 px looks undersized | The new display token gives about 53 px; inbox 440 px left-aligned; nav links from 760 px; 2-column Features and Trust at 601–900 |
| **1366×768** | The CTA bottom is at 584. Notes touch the nav (top 70). The H1 just clears. The scene caption is at the fold edge (751). The How it works step labels sit at the bottom edge | Content-driven hero height; a title row in the How it works frame |
| **1440×900** ([hero](shots/hero-1440.png)) | V2 (the H1 under the cards). 290 px of blank paper under the hero facts. The closer is 4 lines. The Automations machine is cut by the fold (acceptable) | V2 fix; inbox scale; closer `max-width` |
| **1920×1080** ([hero](shots/hero-1920-sorted.png)) | 340 px side margins. The H1 phrase overflows about 80 px. The inbox is 368 px in a 1016 px-tall frame. The caption is at y=1062, detached | Inbox `clamp(380px, 32vw, 480px)`; hero `max-height: 860px`; container width is the owner's call |
