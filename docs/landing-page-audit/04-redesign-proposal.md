# 04 · Redesign proposal

**Summary.** There are three directions. I agree with the researchers' recommendation: **A, "Ink and signal"**. It refines the current paper-and-night system rather than replacing it, uses the four channel colours as the brand's graphic motif, and gets "modern, minimal and bold" from scale and contrast, not new elements. It keeps every owner decision (Geist Bold, C-155 wording, global, no fake proof) and costs S–M. The page goes from 11 sections to 10, alternating paper and night:
- the Strip folds into the hero;
- Integrations merges into Features;
- the setup steps move from Modes to just before Pricing;
- one small "Who it's for" section is added.

**The audit set:** [01 Current state](01-current-state-audit.md) · [02 Visual design](02-visual-design-recommendations.md) · [03 Performance, accessibility and SEO](03-performance-accessibility-seo.md) · 04 Redesign proposal (this file) · [05 Action plan](05-prioritized-action-plan.md) · [06 Design tokens](06-design-token-proposal.md)

Labels: **[Observed]**, **[Measured]**, **[Code]**, **[Hypothesis]**. Each direction is itself a design judgement, so treat it as a hypothesis until it's built and screenshotted.

---

## 1. Three directions

| | **A. Ink and signal** (recommended) | B. Loud editorial | C. Console |
|---|---|---|---|
| **Personality** | Confident, precise, quiet; a product that shows its work | Bold and poster-like, closer to Later | Technical and trustworthy; the page is the app |
| **Palette** | Paper #F5F5F2, sheet #FFFFFF, ink #121317, night #0F1017, iris #4B3FE0 / #A8A1FF. **Channel colours become the system**: Instagram #BE185D, WhatsApp #16A34A, web #0F766E, with comments shown as an Instagram ring (not a second pink); night variants #E0559A and #2AA597 | Paper + ink, with **iris as full-bleed bands** (#4B3FE0 with white text, 6.80:1) replacing some night bands; a channel colour per section header | Night #0F1017 base, #181923 raised, iris-night #A8A1FF; paper only for Pricing and FAQ |
| **Type** | Geist 700 display at two H2 tiers (`--type-h2`, `--type-h2-sm`), Geist 400/500 text, tabular numbers for stats; optional Geist Mono 12 px for "Example data" and status labels (it ships with Geist) | Display `clamp(64px, 7vw, 128px)`, −0.055em, two-to-four-word headlines | Geist 600/700, Geist Mono for data |
| **Hero** | Copy left (≤600 px); a **larger sorted inbox** (≤480 px) on the right, with channel bars and the panel chips "2 need you · 3 AI drafts"; the Strip forms the hero's bottom edge; no long scrub | A full-width headline across 12 columns; the inbox overlaps the band's bottom edge | A large realistic inbox (about 960 px) under a centred headline; "Every DM. Every comment. One inbox." as a tab bar |
| **Sections** | Strict paper/night alternation; one scene per story section; dense utility sections | Few sections, each one statement + one scene | Each section is a framed app view (inbox, knowledge, automation, modes) |
| **Imagery** | Product UI only, plus typographic covers (the Reel). No photos or illustration | Product UI + big type | Product UI |
| **Motion** | One-shot reveals (≤1.2 s); How it works scrub about 200vh; no infinite loops | Line-by-line mask reveals of big type; scenes play once | Subtle state changes inside the frames |
| **Audience fit** | Small businesses and creators who value "it just works" and honesty; it suits a product with no proof yet | Creators skew to it; shops may find it showy | Operators and teams; colder for creators |
| **Trade-offs** | Less instant "wow"; distinction depends on execution detail | **Needs new short headlines**, which breaks the "all wording from the current site" rule (C-155); big iris bands are harder to keep calm | **Close to the old dark design** production still runs (C-152), which the owner moved away from with C-155; looks like many dark SaaS sites |
| **Complexity** | **S–M** (tokens, hero rework, reorder) | M–L | M |

## 2. Recommendation: A, "Ink and signal"

I agree with the researchers. The reasons, from the evidence:

1. **It matches what the owner already chose.** Geist Bold (C-155), paper and night, "modern, minimal and bold", and the C-155 wording rule all stay. B needs new headlines; C reverses C-155.
2. **The system is already sound; the problems are execution.** The colours are fully tokenised and linted, almost every text pair passes AA, and Lighthouse is 94 / 100 [Measured]. The top issues are two bugs, scrub length, heading sizes, spacing and rhythm [Observed]. None of them needs a new direction to fix.
3. **It fixes the "template" risk cheaply.** Paper + Geist + an ink pill button is a widespread 2024–26 look [Hypothesis]. What makes Amplychat its own today is the channel-colour dots and the inbox scenes, which are small: 8 px squares and a 368 px card [Observed]. Scaling those up (channel bars, a larger inbox, Reel covers) is the cheapest way to own the look. No competitor in the review uses channel colour as a system [Observed in `amplychat-competitor-review.html` shots; Hypothesis beyond that set].
4. **"Bold" comes from contrast and scale, not volume.** That means a 68 px H1 with a clear step down to 52 px H2s, an ink CTA as the strongest shape on each band, iris kept for meaning, and strict paper/night alternation.
5. **Honesty is part of the design.** Status dots, "Example data" labels and "coming soon" wording are the proof a product before App Review can show. A keeps them as visible elements, not fine print.
6. **It is the lowest risk for a solo founder.** It is mostly CSS tokens in `globals.css` and `site.css`, one hero rework and a reorder, with no new libraries.

Where I'd push the researchers further:
- **Be strict about motion.** Remove *all* infinite loops, not only the bob, and replace the hero scrub with a one-shot entrance by default. Keep a ≤140vh scrub only if the owner wants it (see the questions in 05). The hero scrub costs 1.5 viewports [Observed], and the scroll-driven hero is the main reason the first frame shows the wrong state.
- **Don't add a colour CTA.** The system audit offers an iris primary button as an alternative. Ink is more "minimal and bold", and it keeps iris meaning "AI did this".

## 3. Proposed page structure

| # | Section | Band | Change from today | Why |
|---|---|---|---|---|
| 1 | **Hero** (with the Strip as its bottom edge on desktop) | paper | Sorted inbox first; no scrub or a short one; H1 fits; audience named (proposal H-2) | Promise and product in the first frame |
| 2 | **How it works**: AI from your knowledge + hand-off | night | Draft bug fixed; about 200vh; title inside the sticky frame; starts with the question | The main differentiator, legible |
| 3 | **Automations**: comment to DM | paper | Reel cover; keyword affordance; summary bar folded into Features | Creator use case |
| 4 | **Modes**: Off / Suggest / Auto | paper-2 | Kicker "AI reply modes" (proposal); setup steps moved out | Control |
| 5 | **Security** | night | Moved up from 8th; leads with what isn't said elsewhere; links `/security` | Answers "is this safe?" early; restores the beat |
| 6 | **Who it's for** (new, small) | paper | Two cards → `/for-creators`, `/for-businesses` | "Is this for me?" without testimonials |
| 7 | **Features + Connections** (merged) | paper | Three clusters + a larger Ask Amplychat card + an integration status grid | Replaces two list sections with one |
| 8 | **Set up in three steps** (moved) → **Pricing** | paper | The steps become a short bridge band into Pricing; 5 key limits shown | Time-to-value next to cost |
| 9 | **FAQ** (trimmed to 6–8) | paper-2 | Objection-led; link to all questions | Shorter page |
| 10 | **Closing CTA** | night | 700 weight, 2 CTAs, email as a text line; a "What's new" liveness line | Clean finish |
| – | Footer | night | Column titles as non-headings; 44 px links on touch | – |

**Rhythm:** paper → night → paper → paper-2 → night → paper → paper → paper (+steps) → paper-2 → night. Sections 6–8 are three light bands in a row. That beats today's four, and "Who it's for" is short. If it still sags in screenshots, give "Set up in three steps" a sheet (#FFFFFF) band. [Hypothesis: verify with a full-page screenshot.]

**Expected length** [Hypothesis]: removing the hero scrub (−1,350 px at 1440), cutting How it works (about −1,250 px), merging Integrations (about −800 px), trimming the FAQ (about −700 px) and tighter same-colour spacing should take the 1440 page from 16,255 px to roughly 11–12k px. Measure after building.

**E2E impact** [Code]: `e2e/landing.spec.ts:60-70` asserts the section order by id. Update it in the same change as the reorder.

## 4. Before and after: the most important changes

| Area | Before [Observed] | After (proposed) |
|---|---|---|
| **AI draft** | A white box with invisible split words while the scene plays ([shot](shots/draft-bug-1440.png)) | The draft types in on the dark card as it does under reduced motion ([shot](shots/draft-reduced-motion-1440.png)) |
| **Hero first frame** | A tilted pile of notes; one covers the full stop of "Every comment."; a "Scroll to sort the inbox" hint ([shot](shots/hero-1440.png)) | The sorted inbox at about 460 px with channel bars and "2 need you · 3 AI drafts" chips; the H1 at 68 px fits its column and sits above the scene; the Strip's top edge is visible as the cue (like [the end state](shots/hero-1920-sorted.png), larger and fuller) |
| **Hero scroll cost** | 2,250 px sticky at 1440 before anything else appears | One viewport (≤860 px) |
| **How it works** | 340vh; it opens on an empty thread with no title in the frame ([shot](shots/decide-empty-frame-1440.png)) | About 200vh; a title row in frame; the question is already there |
| **Headings** | All H2s 58 px; ragged 3–4-line breaks; the closer at 500 | 52 px story / 40 px utility tiers; 2-line headings; everything at 700 |
| **Rhythm** | Four paper bands in a row mid-page ([full page](shots/section-rhythm-1440-full.png)) | Night every 2–3 sections; Security moved up; Features + Integrations merged |
| **Features** | Nine equal items with iris icons ([shot](shots/features-1440.png)) | Three labelled clusters, a large Ask Amplychat card, links to the feature pages |
| **Colour use** | Iris on kickers, icons, step numbers, links, hover … | Iris only for links, focus, selection and AI moments; kickers and icons in ink-3; channel colours carry the brand |
| **Secondary CTA** | Border 1.22:1, near invisible | Border #82848B, 3.42:1 |
| **Motion** | Infinite bob, a 1.9 s feed, 9 s / 16 s / 6 s loops | One-shot reveals; loops stop off screen or after about 5 s |
| **Tablet** | The phone layout with a 46 px H1 and a centred small inbox ([shot](shots/hero-768.png)) | About a 53 px H1, the inbox left-aligned with the copy, nav links from 760 px |
| **Mobile menu** | Doesn't close on an outside tap; three "Start free" buttons at once ([shot](shots/mobile-menu-375.png)) | Closes on outside tap and focus-out; a scrim; one CTA in the menu (Sign in) |
| **Share image** | The old dark card | Paper, the H1 in Geist 700, "One inbox." in iris |
