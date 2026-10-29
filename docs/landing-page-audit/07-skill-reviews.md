# 07 · Skill reviews: Impeccable and Taste Skill

Two design skills the owner installed (2026-10-30) were run read-only on the same page as an independent second opinion. Where they disagree with documents 01 to 06, the differences are listed in section 3, and the owner decides (see the questions in [05](05-prioritized-action-plan.md)).


Area: **skills**. Date: 2026-10-30. Target: http://localhost:3000/ (owner's dev server, read only) and the source in `.claude/worktrees/audit/apps/web` (`src/app/(marketing)/page.tsx`, `src/components/marketing/landing/*`, `src/components/site/site.css`).

This review is an extra, independent pass that uses the two newly installed design skills. It does not repeat B1 (the broken AI draft), B2 (the h1 under the scene) or the other items already in `visual.md`, `system.md` and `perf-a11y.md`. It refers to them only where a skill agrees or disagrees with them.

## How the skills were run, and what was skipped

| Step | Done | Notes |
|---|---|---|
| `impeccable context --target page.tsx` | yes | Reported NO_PRODUCT_MD and EXISTING_VISUAL_SYSTEM: with no PRODUCT.md or DESIGN.md, the incumbent code is the design authority. **Skipped:** `init`/`document` (they would write PRODUCT.md and DESIGN.md into the repo) and hooks. |
| Impeccable critique | yes, **degraded** | `⚠️ DEGRADED: single-context (run as a subagent under the owner's cap on parallel agents; Assessment A was written before any detector output was read)`. **Skipped:** the live-server overlay injection, because its stop step edits the project's entry file; the detector was run against the URL instead. **Skipped:** snapshot persistence to `.impeccable/critique/` (a repo write) and the closing user questions (no user in this run). |
| Impeccable detector | yes | Source scan of the landing TSX found 0 findings, because the patterns live in CSS. URL scans at 1280×800 and 390×844 found 11 each (raw output in `audit/skills/det-1280.json` and `det-390.json`). |
| Impeccable audit and polish | yes | Assessment only; nothing was fixed. |
| Taste `inspect.mjs --film` | yes | 1440, 768 and 390, with screenshots and scroll film in `audit/shots/skills/taste/` and the report in `report.json`. |
| Taste `lint.mjs` | yes | 17 files; output in `audit/skills/taste-lint.txt`. |
| Taste `draw.mjs` | yes | Run from the scratch folder with `--keep palette,type`, so `.taste-skill/` went to `audit/skills/.taste-skill/` and nothing went into the repo. |
| Taste `scenes.mjs`, `assets.mjs` | no | The page has no taste-library scenes. No pictures are being sourced, because this is a review. |

The browsers belonged to the scripts and closed when they finished; no headless browser is left running. Ports 3000 and 8000 were not touched.

---

## 1. Impeccable

### Verdict
The page is **Persuade** mode. Critique scores it **21/32 (66%, Acceptable)**, with heuristics 7 and 9 marked n/a. Audit scores it **13/20 (Acceptable)**. For polish, the skill says the concept is right and should not be redesigned, but the execution is not finished: refine the paper-and-night world that is already there and don't replace it.

**Design specificity: partly authored.** The hero idea, a pile of DMs that scroll into a sorted inbox, is grounded in the product. So are the Off/Suggest/Auto switch and the "LINK" keyword field. From Automations onward, though, the page falls back to a category kit: a kicker, a split head, then a card grid or a ruled list. Features, Integrations and Trust could ship unchanged on respond.io or Wati.

### Heuristics (Persuade mode)
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | The scroll hint and the live mode description both work. During a scrub, the visitor can't see how much scrub is left. |
| 2 | Match with the real world | 3 | "AI credits", "knowledge gap" and "tagged with intent, sentiment and a lead score" go unexplained where they first appear. |
| 3 | User control and freedom | 2 | Two scroll-jacked scrubs, no way to pause the motion, and the menu doesn't close on an outside tap (known). |
| 4 | Consistency and standards | 2 | Two "how" sections. The closing h2 is weight 500. Radii drift. The eyebrow names two channels while the sub-head and strip name three. |
| 5 | Error prevention | 3 | The keyword field and switch can't produce a bad state. |
| 6 | Recognition over recall | 3 | The channel squares rely on remembering a colour code, but they always sit next to a text label. |
| 7 | Flexibility and efficiency | n/a | Landing page. |
| 8 | Aesthetic and minimalist design | 2 | The noise floor is high: 92 rules, 19 outlined boxes, 10 kickers, 16 type sizes and iris in 11+ roles. Nothing is loud, so nothing leads. |
| 9 | Error recovery | n/a | No forms with consequences. |
| 10 | Help and documentation | 3 | The FAQ and Guides exist, but there are 15 FAQs with no grouping. |
| | **Total** | **21/32** | **Acceptable** |

**Cognitive load:** 3 of 8 checks fail (moderate). Visual hierarchy fails because every h2 is the same size and 3–4 lines long. Chunking fails with 9 features, 8 integrations and 15 FAQs in flat lists. Minimal choices fails with three actions in the closer and seven controls in the header.

**Emotional journey:** the peak is the Decide scene ("it doesn't guess: it hands the conversation to you"). That is the most reassuring moment on the page, and it is currently broken (B1). The valley is the four paper bands in a row (V2). The end is a closer with three CTAs at weight 500, so the page ends softer than it starts. By the peak-end rule, the Decide scene and the closer matter more than the Features grid.

### Detector (deterministic)
- **overused-font: Geist, 100% of text (warning).** **This is a conflict with the brief, not a finding to act on.** Geist Bold is the owner's choice, and Impeccable's own rule is "the brief wins". The lesson is the one in `visual.md` §1: since the face is the 2024–26 default, any distinctiveness has to come from scale, the motif and the product scenes.
- **straggler (advisory), 9 at 1280 and 6 at 390.** One-word last lines in `li.mi p` (Features: "account.", "checked."), `li.crow p` (Integrations: "inbox.", "Page.", "ad.", "step.", "arrive."), `li.tr p` (Trust: "APIs.", "password.", "encrypted."), `.plan.main .sub` ("trial."), and on the phone in `p.bub.in` and `p.mode-desc`. **New:** none of these paragraph classes sets `text-wrap: pretty`; only `.lede` and `.hero-sub` do. Fix: add `text-wrap: pretty` to body paragraphs inside `.site`. P3, effort S.
- **unbalanced-heading (advisory), 1 at 1280 and 4 at 390.** All are FAQ `summary > h3` (questions 4, 5, 9 and 12). **New:** `text-wrap: balance` is on `.h1`/`.h2` but not on the FAQ h3. P3, effort S.
- Nothing else fired: no gradient text, no glassmorphism cards, no nested cards, no side-stripe borders. Impeccable's slop detector rates this page cleaner than Taste's inspector does (see §3).

### Priority issues (only the new ones or a new angle; known bugs are by reference)
1. **[P1] Specificity drops after the first screen.**
   - **Where:** `Features.tsx`, `Channels.tsx`, `Trust.tsx`.
   - **Why it matters:** the hero passes the cover-the-logo test, but the middle of the page doesn't. A visitor scrolling fast sees a generic SaaS kit exactly where the differentiators (Ask Amplychat, comment intelligence, knowledge gaps) are listed.
   - **Fix:** carry the system's own motif through instead of icon tiles. The motif is the note card, with its channel square, sender, message and tag. Features become real note-card fragments (a "Needs you" card, an "AI draft" card with its sources, a comment-intelligence bar), not tiles with a Lucide icon.
   - **Command:** `/impeccable bolder` scoped to Features. P1 · effort M.
2. **[P1] Peak-end mismatch.**
   - **Where:** Decide (peak) and FinalCta (end).
   - **Why it matters:** the strongest promise ("doesn't guess") sits mid-page at the same visual weight as everything else, and the page ends on its weakest frame: weight 500, four lines, three actions.
   - **Fix:** make Decide the single loud section, with the heading inside the sticky frame at a larger tier. In the closer, one action, weight 700, and repeat the "doesn't guess" promise in words already on the site.
   - **Command:** `/impeccable layout`. P1 · S–M.
3. **[P2] The noise floor undermines "minimal".**
   - **Where:** `site.css`. The strip's `li + li` border (:177), `.nav` border-bottom plus blur (:95), integration and feature row rules, the outlined `.btn-line`, and kickers on all 10 sections.
   - **Why it matters:** "minimal" comes from removing these separators, not from keeping the palette small. Today every band is fenced off twice: by colour and by a rule.
   - **Fix:** outside the product scenes, separate with space and the paper/paper-2/sheet tone steps already in the palette, and drop the rules.
   - **Command:** `/impeccable quieter` on the chrome, then `/impeccable distill`. P2 · S.
4. **[P2] Global positioning leak.**
   - **Where:** Features ("Send a Razorpay link or a UPI request") and Integrations ("Razorpay and UPI", "Your own account").
   - **Why it matters:** these are India-only payment rails. They are listed as headline capabilities on a page positioned globally, whose sample data uses Toronto. A visitor in the US or EU reads this as "not for me" or "unfinished". None of the existing audits mention it.
   - **Fix (owner's call, because the wording comes from the current site):** label the region ("Razorpay and UPI (India)"), or move payments to the end of the Integrations list. Don't invent Stripe support.
   - **Command:** `/impeccable clarify`. P2 · S.
5. **[P2] The first screen contradicts itself on channels.**
   - **Where:** `Hero.tsx:34` eyebrow, "AI inbox and automations for Instagram and WhatsApp", against the sub-head and strip, which both include the website.
   - **Why it matters:** the first thing a visitor reads drops one of the three channels. `system.md` #11 catches this in the metadata only, and `visual.md` H-1 even proposes "AI inbox for Instagram and WhatsApp" as the eyebrow.
   - **Fix:** delete the eyebrow (see Taste) or use the three-channel line.
   - **Command:** `/impeccable clarify`. P2 · S.

### Persona red flags
- **Jordan (first-timer):** "200 AI credits" in the strip, with no clue what one credit buys until the FAQ, 12 screens later. "Knowledge gap" and "lead score" in the Decide step labels are unexplained.
- **Riley (stress tester):** the AI draft breaks while motion is on (B1, known). Under reduced motion, 5 hero time labels ("31m", "26m", "12m"…) sit at `opacity: 0` (`site.css:164` `.time { opacity: var(--tm, 0) }`) but stay in the accessibility tree, so a screen reader announces times that sighted users never see. Fix: put `aria-hidden` on `.time`, or move it out of the rendered state. P3 · S. **New; `perf-a11y.md` §2.4 calls the reduced state "complete".**
- **Casey (phone):** the first screen works (CTA at 539px). After that, the page is about 18 screens at 1440 and about 20k px on a phone (known). The FAQ alone is 15 taps.

### Impeccable audit (technical, 0–4)
| Dimension | Score | Key finding |
|---|---|---|
| Accessibility | 3 | Already strong (see `perf-a11y.md`). Adds: hidden `.time` text still announced; the 11px Pro badge. |
| Performance | 3 | Agrees with `perf-a11y.md`. `will-change` is narrowly scoped (good). Read/write interleaving in decide (known). |
| Theming | 3 | Tokens throughout and a lint against literals. The `.scan` gradient on night is the one decorative effect. |
| Responsive | 2 | Tablet gets the phone layout and the h1 drops to its floor (known). Four headings run 3 lines at 390. |
| Implementation integrity | 2 | B1/B2, the placeholder Reel tile, two "how" sections and the eyebrow mismatch are verified. Coherent system, unfinished execution. |
| **Total** | **13/20** | **Acceptable** |

---

## 2. Taste Skill (tasteskill v2)

### Verdict
The inspector returns **12 FAIL and 4 WARN**. The lint returns **44 FAIL and 19 WARN** across 17 files. The critique round below is capped at **6.0 overall**: any open FAIL caps the score at 6.0, and the headline covered by the notes (B2) caps usability at 6.

```
ROUND 1 (review only)
Seen in one second: the black "Every DM. Every comment." with scattered white note cards; then "One inbox." in iris.
Idea (one sentence): On this page, the owner's messy pile of DMs and comments becomes the sorted inbox.
  Competitor test: still works for respond.io or Wati, so it is the category's idea. The parts only Amplychat owns:
  the AI that refuses to guess and logs a knowledge gap, Off/Suggest/Auto per account, comment "LINK" → DM.
Live thing: yes, two. The Off/Suggest/Auto switch (Modes) and the editable keyword field (Comments). Both work by keyboard and without motion.
Layout words by section: hero=split-scene / strip=4-up ruled row / decide=split-scene / comments=3-card row /
  modes=table / steps=3-up / features=3×3 icon grid / integrations=ruled list / trust=3-up / pricing=card row /
  faq=accordion list / close=split-scene.  "3-up" appears 4 times; that is the template showing.
Scores: design 6 · usability 6 · creativity 6.5 · content 7.5 → 6.25, capped to 6.0
Caps applied: open FAILs (≤6.0); headline covered by the scene at 1440 (usability ≤6); 3+ line headlines,
  eyebrows, "Step 1/2/3", decorative hairlines and shadows at rest (≤6.5); idea passes the competitor test (creativity ≤7).
Top three problems:
1. Headlines over two lines at 1440 and 390 (hero 3, Features 3, Trust 3, closer 4); the hero line runs under the
   notes (desktop-fold.jpg). Fix: widen the measure before touching size; keep "Every DM. Every comment." as the h1
   and move "One inbox." to its own line only if it still fits two lines.
2. The chrome is made of ornaments: 10 kickers, 92 thin rules, 19 outlined boxes, 6 resting shadows, a blurred nav,
   and the .scan gradient (desktop-page-02/03.jpg). Fix: delete the kickers, separate with tone steps, and mark the
   product scenes data-ui so their own borders stay.
3. Middle of the page is the stock "3-up" kit: Comments (3 cards), Steps (3-up "Step 1"), Features (9 icon tiles),
   Trust (3-up) (desktop-page-03.jpg). Fix: one composition per section from the dealt blueprints (below).
```

### Inspector and lint findings that the existing audits don't have
| # | What | Where | Why it matters | Fix | Sev · Effort |
|---|---|---|---|---|---|
| T1 | **10 eyebrow/kicker labels.** Every section opens with "How it works", "Automations", "Features", "Integrations"… The hero eyebrow carries channel dots. | `Hero.tsx:34`, `Decide.tsx:40`, `Comments.tsx:43`, `Modes.tsx:39`, `Features.tsx:78`, `Channels.tsx:89`, plus 4 more | They repeat the nav and push every heading down by 32px. The study puts this among the top tells of generated pages. The existing audits keep them and only rename or recolour them. | Delete them. Where one carried information (Modes: "Set up in three steps"), put it in the h2 or the lede. | Medium · S |
| T2 | **Decorative hairlines and outlined boxes:** 92 rules, 19 outlined boxes, 1 dashed border | `site.css` :95, :111, :117, :126, :154, :174, :177 and the `.crow` and `.mi` rows | Fences every block, which reads as busy rather than minimal. | Outside product scenes, use space and tone steps. Keep rules inside real tables (Modes `role=table`) and inside the product fragments. | Medium · S |
| T3 | **Product scenes are not marked as interface fragments.** The inspector counts **0 pictures** and judges the scenes' own borders, shadows and the `.panel` shadow as page chrome. | `.inbox`, `.thread`, `.kb`, `.post`, `.dm`, `.mtable` roots | The page has no pictures, so its scenes are its only imagery. Today they read as page boxes, not as the product. Mark each scene root `data-ui` (a no-op attribute), make them larger, and give them the real app's density. That alone takes the scenes out of 3 of the 12 FAILs and makes the "show the product" story explicit. | `data-ui` on scene roots; hero inbox at 40%+ of the first screen | Low · S |
| T4 | **Icon-topped card rows**, three of them: 3 Comments cards, a 9-tile Features grid with a Lucide icon on each tile, and 5 Trust/Steps tiles | `Features.tsx`, `Comments.tsx`, `Trust.tsx` | This is the strongest "kit" signal on the page. `visual.md` proposes grouping into 3 clusters, which keeps the tiles. | Features as a poster-scale list: capability names large down the left, one sentence each on the right, no icons. Promote Ask Amplychat by position. | Medium · M |
| T5 | **"Step 1 / Step 2 / Step 3" index labels** | `Modes.tsx:93` | Banned as house style. The order is already carried by position and by the `<ol>`. | Drop the "Step n" span; keep the `<ol>`. | Low · S |
| T6 | **Body text at 15px** in the strip, features and integrations; 18 text blocks under 13px | `.strip-in li`, `.mi p`, `.crow p`; `.tag`, `.pl`, `.note-top` | At 15px grey, the page reads quieter than "bold". | Running text at 16px in full ink-2; nothing that must be read under 13px (the scene meta can stay at 12–13 inside `data-ui`). | Low · S |
| T7 | **Hidden text under reduced motion** (5 hero time labels) | `site.css:164` | Same as the Riley flag above: in the a11y tree but invisible. | `aria-hidden` on `.time`. | Low · S |
| T8 | **Gradient** `.scan` on night | `site.css:198` | The only gradient on the page. It makes the knowledge scan look "AI-glowy". | A flat iris-night tint at fixed opacity. | Low · S |

The taste meter's 3-line headlines and the 1.1:1 draft contrast are B2/V4 and B1, which are already reported. They are confirmed here and not repeated.

### What the Taste meter gets wrong or over-weights here
- **`few-pictures` / `no-footage`.** No photograph honestly belongs on this page: there are no customers and no team shots, and stock "business owner on phone" photos would be filler. The skill's own rule says software shows its own interface. The right response is T3: mark the HTML scenes as interface, and later add **one real capture of the real dashboard on demo data** as the moving picture. That is honest because the app exists. No archive photos.
- **`reduced-hidden`** is technically right, but its stated fix ("everything visible under reduced motion") is wrong for the time labels. In the sorted state the time is replaced by the tag on purpose, so hide it from the accessibility tree instead (T7).
- **"No violet" house rule.** Iris `#4B3FE0` is exactly the first-wave "assistant palette" Taste bans. It is a brand choice from the owner's design file, so per Impeccable's "the brief wins" and Taste's own `--keep palette` route, it stays. What both skills do support is `system.md` #7: limit iris to the action and to "AI did this", so it signals something instead of decorating.

### Phone
The 390 sheets show the phone as a real composition: the inbox sits under the CTAs, the strip is 2×2 and the scenes are stacked. Problems: 4 headings run 3 lines; the eyebrow wraps (known); and the Reel tile is a grey box with a camera icon (V7, known), which Taste caps as a placeholder (content ≤5 if left).

---

## 3. Agreement and disagreement with the existing audit

| Topic | visual / system / perf-a11y | Impeccable | Taste | Net |
|---|---|---|---|---|
| B1 draft, B2 h1 overlap | Critical / High | Agrees (P1, implementation integrity) | Agrees (contrast FAIL 1.1:1; headline covered caps usability) | **All agree** |
| 3–4 line h2s, single h2 size, closer at 500 | V3/V4 | Agrees | Agrees, stricter: ≤2 lines at **every** width including 390 | Agree. Taste adds the phone. |
| Rhythm sag, 4 paper bands; merge Integrations into Features | V2 | Agrees (emotional valley) | Agrees (sameness pass) | Agree |
| **Kickers** | Keep them; rename (V-§4) and recolour to ink-3 (system #7) | Neutral; counts them as noise floor | **Delete all 10** | **Disagree.** Both skills favour removing them over restyling them. |
| **Direction A: Geist Mono labels, "section index marks" from channel bars** | Recommended (visual §9 A) | Against adding a new primitive in a refinement ("no new font or system primitive") | **Bans** monospace labels and index marks outright | **Disagree.** Keep direction A's channel-colour idea, but as the note-card motif, not as mono labels or index marks. |
| **Setup steps as "a compact numbered row"** | visual §4 Modes | Neutral | Bans "Step n" | Disagree: keep the `<ol>` and drop the visible numbers. |
| Nav "1px rule plus soft shadow after scroll" (V9) | Proposed | Fine | Allows a shadow on a sticky bar; bans the rule and the blur | Partial: solid paper with a shadow only once scrolled, no rule, no blur |
| Hairlines and outlined boxes | Treated as fine (rule tokens kept "for hairlines") | Noise floor (P2) | FAIL (92 / 19) | **New emphasis.** The existing audits don't question them. |
| Iris accent | Keep, but reduce from 11 roles (system #7) | Brief wins; agrees with reducing | Bans violet; overridden by the brand | Agree on reducing; keep the colour |
| Geist | Hypothesis: "a widespread modern default" (visual §1) | Detector: overused font | Default-font warning | Agree it's generic; **the owner's choice stands**, so distinctiveness has to come from scale and motif |
| Reduced motion "complete and meaningful" | perf-a11y §2.4 | Mostly agrees; flags hidden `.time` in the a11y tree | FAIL `reduced-hidden` | **Small disagreement** (T7) |
| Razorpay/UPI on a global page | Not mentioned | P2 | n/a | **New** |
| Eyebrow omits website chat | visual H-1 keeps a two-channel line | P2 | Delete the eyebrow | **Disagree** with H-1 |
| Missing `text-wrap: pretty` / balance on body and FAQ | Not mentioned | 15 stragglers, 4 unbalanced FAQ h3s | n/a | **New**, trivial fix |
| Pictures | "Product UI only, no photos" (visual §9 A) | Agrees | Wants ≥4 real pictures | Agree with visual; meet Taste's intent through `data-ui` scenes plus one real app capture |

---

## 4. Best visual direction for "modern, minimal and bold"

### Impeccable: refine, don't replace; then make one section bold
- Treat the paper-and-night world, Geist Bold and iris as fixed. This is refinement, so a new direction is out of scope.
- **Minimal** comes from subtraction:
  - drop the kickers, the decorative rules and the second "how" section;
  - collapse 9 features into fewer, larger items, and 15 FAQs into about 6–8 grouped ones.
- **Bold** comes from one decisive amplification of something the system already owns, not from turning everything up:
  - The **note card plus channel square** becomes the page's single motif, from the hero pile through features and integration rows to the closer.
  - **Decide** ("doesn't guess") becomes the page's single peak: a larger heading tier, the heading inside the sticky frame, and nothing else on the page as loud.
  - The **closer** matches the hero: weight 700, two lines, one action.
- Don't add Geist Mono or other new primitives.

### Taste Skill: dealt "Colour chapters" (seed 270029103, palette and type kept)
Of the three directions dealt (`one-motif`, `colour-chapters`, `loud-flat-poster`), **colour-chapters** fits best. The owner's paper/night alternation already is a chapter system. Taste would make it strict:
- **Chapters:** full-bleed fields butting directly against each other, with no rules and no gaps. Colour means something: paper is "you", night is "the AI working", and one iris field is the action.
- **Headlines:** two lines or fewer at every width, on one shared left edge, at a larger display size.
- **Hero:** the dealt "tabbed folder stack" is redrawn here because it needs condensed caps and a serif, which conflicts with the kept Geist-only type. In its place, the hero inbox goes to 40% or more of the first screen as a `data-ui` fragment.
- **Section blueprints worth taking as they are:**
  - *Features as a poster-scale list*, with names at 40–84px and one sentence each; no icons, no tiles.
  - *Stages as one bar* for How it works / the setup: the four Decide stages as one segmented bar.
  - *FAQ as bands*: alternating paper/paper-2 bands with all answers visible. This forces the cut to about 6 questions.
  - *CTA inverted*: a night field, the hero's idea in two lines, one button.
- **The one live thing stays as the Off/Suggest/Auto switch.** Taste's "one control, blown up" blueprint fits it exactly: the switch at poster scale, where flipping it changes the rows and one word of the heading.
- Taste would also cut the `loud-flat-poster` option: it needs new wording and saturated fields beyond the brand palette. Like `visual.md` direction B, it conflicts with the wording rule.

### Where the two skills land together
Both favour **subtraction plus one amplified motif**:
- remove the kickers, rules, icon tiles and step numbers;
- keep paper/night, Geist Bold and iris (limited to the action and AI);
- make the product scenes bigger and treat them as the page's only imagery;
- give the page one peak (Decide, or the switch at poster scale) and an ending as strong as the opening.

This is close to `visual.md` direction A **without** its Geist Mono labels and index marks.

