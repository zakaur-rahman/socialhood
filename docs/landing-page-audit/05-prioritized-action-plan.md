# 05 · Prioritised action plan

**Summary.** There are 44 tasks in five phases. Phase 1 fixes what visitors see broken today: the draft box, the H1 overflow, the secondary-CTA border and the menu. These are all S, and they could ship as one small PR. Phase 2 is the hero rework, the reorder and the heading and spacing system that make the page feel "modern, minimal and bold". Phases 3–5 cover responsive, interaction, performance, a11y and SEO work, then the final validation. The 12-category scorecard and the owner questions are at the end.

**The audit set:** [01 Current state](01-current-state-audit.md) · [02 Visual design](02-visual-design-recommendations.md) · [03 Performance, accessibility and SEO](03-performance-accessibility-seo.md) · [04 Redesign proposal](04-redesign-proposal.md) · 05 Action plan (this file) · [06 Design tokens](06-design-token-proposal.md)

**How verification works** (owner rule, 2026-10-25): locally, run only e2e and UI screenshots, plus any fix that blocks them. Open the PR and let CI run the rest (unit tests, lint including `design-lint.test.ts`, type check, build).
- **e2e:** `pnpm e2e -- --grep "landing page"` runs `apps/web/e2e/landing.spec.ts` (scenes filled and live, section order, no sideways scroll, CLS <0.1 at 375, 768, 1280 and 1536).
- **Screenshots:** a Playwright pass at 375×812, 768×1024, 1440×900 and 1920×1080, with motion on and with `prefers-reduced-motion: reduce`, the same method as this audit. Compare against `docs/landing-page-audit/shots/`.

Effort: S = hours, M = a day or two, L = more. Paths are relative to `apps/web/src/`.

---

## Phase 1: critical fixes

| ID | Task | Files / components | Depends on | Effort | Acceptance criteria | Verify |
|---|---|---|---|---|---|---|
| LP-1.1 | **Fix the AI draft collision**: rename the DM typing-dots class to `.dm-typing` | `components/site/site.css:280-283`, `components/marketing/landing/landing-motion.ts:466` | – | S | `p.ddraft-t` keeps a transparent background and block layout at every scrub progress; the draft is readable at 1440 and 375; the DM dots in Automations still animate | Screenshots of the decide scene at p = 0.5 and 1.0 (1440, 375). Add an assertion to `landing.spec.ts`: computed `background-color` of `.ddraft-t` is transparent once the scene is live. `pnpm e2e -- --grep "landing page"` |
| LP-1.2 | **Fix the H1 overflow**: display token, 1fr/1fr hero grid above 1060 px, copy above the stage | `site.css:49, 133`; `.hero-copy` | LP-2.1 (or inline the value first) | S | At 1061, 1280, 1366, 1440, 1920 and 2560 the "Every comment." right edge ≤ the copy column's right edge; no note overlaps the H1 | Screenshots at 1440 and 1920; an e2e check comparing the `.phrase` rect against `.hero-copy` |
| LP-1.3 | **Secondary CTA borders to 3:1**: #82848B on paper, #6A6C76 on night | `styles/globals.css` (new tokens), `site.css` `.btn-line` + the night override | LP-2.1 | S | The border is ≥3:1 on paper, paper-2 and night | Screenshot the hero and the closer; CI contrast test (LP-4.7) |
| LP-1.4 | **Mobile menu**: close on outside `pointerdown` and on `focusout` from the panel; remove "Start free" from the menu actions; menu buttons 48 px; header CTA 44 px at ≤900 | `components/marketing/MobileMenu.tsx`, `SiteHeader.tsx`, `site.css` `.nav .btn` | – | S | An outside tap closes it; Tab past the last item closes it; one "Start free" visible with the menu open; header CTA ≥44 px tall | e2e: open the menu at 375, click the hero, expect `aria-expanded=false`; screenshot the menu open |
| LP-1.5 | **Closing H2 to weight 700**, `max-width: 14ch` | `site.css:391` | – | S | The closer is 700 and ≤3 lines at 1440 | Screenshot of the closer at 1440 and 375 |
| LP-1.6 | **Knowledge-line dimming readable**: dim to `--night-ink-3` (5.52:1) instead of opacity .5 / .35 | `site.css` `.kb.scanning .line`, `.kb.miss .line` | – | S | Dimmed lines ≥4.5:1 | Screenshot of the decide scene mid-scan |

## Phase 2: high-impact visual

| ID | Task | Files / components | Depends on | Effort | Acceptance criteria | Verify |
|---|---|---|---|---|---|---|
| LP-2.1 | **Add the site scale tokens** (type, spacing, radii, motion, containers, the new colours) to `@theme` and the `.site` aliases | `styles/globals.css` (`@theme` and `.site` block `:504-564`); spec in [06](06-design-token-proposal.md) | – | M | The tokens exist and are generated into `tokens.generated.*` by `pnpm tokens`; nothing renders differently yet | CI (lint, tokens); a screenshot diff shows no change |
| LP-2.2 | **Two heading tiers + wider heading column**: `--type-h2` for story sections, `--type-h2-sm` for utility sections; split-head `1.25fr / .75fr`; `max-width: 18ch` | `site.css:51, 236`; `Faq.tsx`, `Channels.tsx`, `Trust.tsx` (tier class) | LP-2.1 | S | No section H2 is over 3 lines at 1366–1920; "Common questions" is one line at ≥1061 | Screenshots of every section at 1440 |
| LP-2.3 | **Hero rework**: sorted inbox at load; scrub removed (or ≤140vh, per the owner's answer); one-shot sort ≤1.2 s; inbox `clamp(380px, 32vw, 480px)`; hero `min(100svh - 64px, 860px)`; remove the bob and the scroll hint; stage caption → an "Example data" label | `components/marketing/landing/Hero.tsx`, `landing-motion.ts` (hero scene), `site.css:131-160` | LP-1.2, owner question 2 | M | The first frame shows the sorted inbox at all widths; the next section's top edge is visible at 1366×768; no infinite animation in the hero | `landing.spec.ts` ("scenes are filled and live" still passes; update its hero expectations); screenshots at four widths, motion on and off |
| LP-2.4 | **How it works**: scrub 340vh → about 200vh; title row inside the sticky frame; question pre-filled; `.thread-b` min-height 380 px (auto ≤900); lift the step labels | `Decide.tsx`, `landing-motion.ts` (decide scene), `site.css:180-205` | LP-1.1 | M | The sticky frame shows the title at every progress; no empty thread frame | Screenshots of decide at p = 0, 0.5 and 1 at 1440 and 1366 |
| LP-2.5 | **Reorder sections**: Hero → How it works → Automations → Modes → Security → Who it's for → Features + Connections → Steps + Pricing → FAQ → Closing | `app/(marketing)/page.tsx`; `e2e/landing.spec.ts:60-70` | LP-2.6, LP-2.7, LP-2.8 | S | The bands alternate as in [04](04-redesign-proposal.md); the e2e order matches | `pnpm e2e -- --grep "landing page"`; a full-page screenshot at 1440 |
| LP-2.6 | **Merge Integrations into Features**: three clusters, a larger Ask Amplychat card, a status-chip grid, drop "Chat widget", links to `/features/*`; remove the inline `paddingTop: 40` | `Features.tsx`, `Channels.tsx:85`, `site.css` | LP-2.1 | M | One section; statuses still shown as text; links present | Screenshots at 1440 and 375; e2e order |
| LP-2.7 | **Move the setup steps** out of Modes into a bridge band before Pricing; Modes kicker "AI reply modes" (copy proposal; owner to confirm) | `Modes.tsx`, `Pricing.tsx` or a new small component, `page.tsx` | – | S | Modes is about modes only; the steps sit directly above Pricing | Screenshots |
| LP-2.8 | **"Who it's for"** cards → `/for-creators`, `/for-businesses`, using the wording already on those pages | New `components/marketing/landing/Audience.tsx`, `page.tsx` | Owner question 5 | S | Two cards, no new claims; both links work | e2e: links resolve (200); screenshots |
| LP-2.9 | **Spacing scale**: section, tight-section and head gaps; fluid gutters | `site.css` (`.sec`, `.close`, `.decide-head`, `.split-head + *`, `.wrap`) | LP-2.1 | S | Same-colour neighbours ≤ about 210 px apart (today 272); one head-gap value | A full-page screenshot at 1440 and 375; record the page height |
| LP-2.10 | **Accent discipline**: kickers, `.steps .n` and feature icons → ink-3 or ink; primary hover → #3A2FC2 | `site.css` (`.kicker`, `.steps .n`, `.mi-h svg`, `.btn-main:hover`) | LP-2.1 | S | Iris appears only on links, focus, selection, "One inbox." and AI elements | Screenshots at 1440 |
| LP-2.11 | **Channel colours as a motif**: 3 px left bar per note and row; comments as an Instagram ring; night variants #E0559A and #2AA597 | `site.css` (`.note`, `.cmt`, mini inbox), `globals.css` | LP-2.1 | S | All marks ≥3:1 on their background | Screenshots of the hero, decide and closer |
| LP-2.12 | **Strip**: values at `--type-stat-sm` with tabular numbers; replace the duplicate "Official Meta APIs" (fact-check the replacement); on desktop it sits as the hero's bottom edge | `Strip.tsx`, `site.css` | LP-2.3, owner question 6 | S | Values ≥24 px; no duplicate fact | Screenshot at 1366×768 (visible above the fold) |
| LP-2.13 | **Reel cover**: a typographic cover in place of the grey video icon | `Comments.tsx:56-59`, `site.css` | – | S | No placeholder icon | Screenshot of Automations |

## Phase 3: responsive and interaction

| ID | Task | Files | Depends on | Effort | Acceptance criteria | Verify |
|---|---|---|---|---|---|---|
| LP-3.1 | **Tablet tier**: H1 via the display token (about 53 px at 768); inbox 440 px left-aligned; 2-column Features and Trust at 601–900 | `site.css` media blocks | LP-1.2, LP-2.1 | S | At 768 the H1 is ≥50 px and the inbox's left edge aligns with the copy | Screenshot at 768×1024 |
| LP-3.2 | **Header breakpoint to 760 px**: links visible on tablets, 20 px gap at 761–1060; update the JS mirrors | `site.css`, `SiteHeader.tsx:11`, `landing-motion.ts:38` (read from tokens, LP-4.6) | LP-2.1 | S | Five links visible at 768 with no wrap | Screenshot at 768; e2e at "tablet" still passes |
| LP-3.3 | **Phone hero**: full-width "Start free" + text-link secondary; eyebrow proposal H-1; `.panel-h .num { white-space: nowrap }`; sort once on view (no 9 s loop) | `Hero.tsx`, `site.css`, `landing-motion.ts:69-75` | LP-2.3 | S | No orphaned "WhatsApp"; "8 conversations" on one line; no loop | Screenshots at 375 and 430 |
| LP-3.4 | **Header scrolled state**: solid paper + rule + soft shadow after 8 px, via one IntersectionObserver sentinel | `SiteHeader.tsx`, `site.css:93-96` | – | S | No grey slab over night bands | Screenshots at a band boundary at 1440 |
| LP-3.5 | **Touch targets**: "Compare every plan limit", footer links (44 px at ≤900), Privacy link, footer email ≥24 px (44 on touch) | `Pricing.tsx`, `SiteFooter.tsx`, `Trust.tsx`, `site.css` | – | S | Every standalone link is ≥24 px tall, and ≥44 px at ≤900 | A DOM measurement script in the screenshot pass |
| LP-3.6 | **Keyword field affordance**: iris 1.5 px border at rest; label "Try your own keyword" (proposal) | `Comments.tsx`, `site.css` | – | S | The field reads as interactive at rest | Screenshot; e2e keyword test still passes |
| LP-3.7 | **Closer**: two CTAs; the email as a text line | `components/marketing/FinalCta.tsx` | – | S | Two buttons only | Screenshots at 1440 and 375 |
| LP-3.8 | **FAQ trim** to 6–8 objection-led questions plus a link to the rest (the FAQPage JSON-LD follows automatically from `lib/marketing/faq.ts`) | `lib/marketing/faq.ts`, `Faq.tsx`, a new or existing FAQ page | Owner question 7 | S–M | The visible FAQ and the JSON-LD still match | e2e; view source for the JSON-LD |
| LP-3.9 | **Pricing compaction**: 5 decisive limits shown, the rest collapsed | `Pricing.tsx`, `PlanMatrix.tsx` | – | S | The plan cards' key limits are visible in one 1440 fold | Screenshot |

## Phase 4: performance, a11y and SEO

| ID | Task | Files | Depends on | Effort | Acceptance criteria | Verify |
|---|---|---|---|---|---|---|
| LP-4.1 | **Motion pause (WCAG 2.2.2)**: stop every infinite animation and the comment timer when off screen or after about 5 s; remove the closer's `.falling` loop | `landing-motion.ts`, `site.css` keyframes | LP-2.3 | S–M | No animation runs longer than 5 s without user action | e2e: after 8 s, `document.getAnimations()` has no running infinite animation |
| LP-4.2 | **Measure Sentry on production (R-1)**, then trim Replay or delay loading | `instrumentation-client.ts`, `next.config.ts` (`withSentryConfig`) | – | S | A measured answer; if confirmed, the chunk is smaller or loads after first interaction | Lighthouse on production (CI or manual), network panel |
| LP-4.3 | **`decideScene` read/write batching** + rAF-debounced `resize` | `landing-motion.ts` | LP-2.4 | S | No forced reflow per line in a DevTools trace | DevTools Performance at 4x CPU |
| LP-4.4 | **A11y small fixes**: the `/pricing` H2 (A-2), the menu nav name (A-4), logo `aria-hidden` (A-6), the "AutoPro" name (A-12), 11 px → 12 px (A-14) | `Pricing.tsx`, `MobileMenu.tsx`, `primitives.tsx`, `Modes.tsx`, `site.css` | – | S | axe shows 0 violations on `/pricing` | The axe run in CI |
| LP-4.5 | **Share image redraw**: paper, the H1 in Geist 700, iris "One inbox."; drop the C-129 exception | `components/marketing/og.tsx`, `styles/colour-exceptions.ts:93` | Owner question 3 | S–M | `/og.png` matches the site | Open `/og.png` locally (screenshot) |
| LP-4.6 | **Breakpoints from tokens in JS**: `SiteHeader.tsx` and `landing-motion.ts` read `tokens.generated.ts`; fix `--nav-h` being read from `<html>` | `SiteHeader.tsx:11`, `landing-motion.ts:38-39`, `lib/breakpoints.ts` pattern | LP-2.1 | S | No 901 literal in TS | CI |
| LP-4.7 | **Site contrast tests**: add the paper and night pairs (about 40) to `contrast.test.ts` | `styles/contrast.test.ts`, `styles/tokens.ts:109-122` | LP-2.1 | S | Each pair from [06](06-design-token-proposal.md) is asserted | CI |
| LP-4.8 | **Metadata positioning**: one line naming website chat (and comment-to-DM) across the title, description, `SITE_TAGLINE`, the root default description, the footer about-line and `llms.txt` | `lib/marketing/site.ts`, `seo.ts`, `llms.ts`, `app/layout.tsx:25` | Owner question 4 | S | All lines consistent; title ≤60 and description ≤160 (existing tests) | CI; view source |
| LP-4.9 | **SEO hygiene**: footer column titles as `<p>` + `sr-only` H2; scene H3s → `<p>`; canonical slash alignment; add `automations`, `modes` and `security` to `SECTION_IDS`; `data-nosnippet` on scenes | `SiteFooter.tsx`, `Decide.tsx`, `seo.ts`, `lib/marketing/site.ts`, `Comments.tsx:39`, `Modes.tsx:193`, `Trust.tsx` | LP-2.5 | S | A clean heading outline | e2e order test uses `SECTION_IDS`; CI |
| LP-4.10 | **In-body deep links**: Features → `/features/*`; Automations → the comment-to-DM guide; Connections → the WhatsApp API guide | `Features.tsx`, `Comments.tsx` | LP-2.6 | S | All links resolve | e2e link check |

## Phase 5: polish and validation

| ID | Task | Files | Depends on | Effort | Acceptance criteria | Verify |
|---|---|---|---|---|---|---|
| LP-5.1 | **Radius scale** applied (5 steps) | `site.css` | LP-2.1 | S | Only token radii in `site.css` (plus 50% and 999 px) | grep; screenshots |
| LP-5.2 | **Semantic `--s-*` aliases re-pointed in `.night`**; delete the 12 `.night` overrides | `globals.css`, `site.css` | LP-2.1 | M | Zero `.night .x` colour overrides; nothing changes visually | A full screenshot diff |
| LP-5.3 | **State class naming**: `is-*` for states, starting with the scenes (`.line`, `.hit`, `.seen`, `.on`) | `site.css`, `landing-motion.ts` | LP-1.1 | M | No bare-word state class in the scenes | Screenshots of every scene; e2e |
| LP-5.4 | **Retire leftovers**: `MARKETING_CARD*` (`classes.ts`); re-point `--gradient-brand` and `--color-brand-deep` in `.site`; `brand-strong` in `.night` → iris-night | `components/marketing/classes.ts`, `globals.css:537-584` | LP-2.1 | M | Public pages show one button look | Screenshots of data-deletion and unsubscribe |
| LP-5.5 | **Exempt `.site` from the 400/500/600 rule** with a comment at `globals.css:455` (C-155) | `globals.css` | – | S | Comment present | – |
| LP-5.6 | **Final validation**: screenshot pass at six widths, motion on and off; e2e; Lighthouse (production build, 3 runs, medians); axe on five pages; update this scorecard | – | All | M | No Lighthouse category drops below the baseline (mobile Performance ≥94, the rest 100); the draft is readable; page height recorded | As listed; record the results in CONFLICTS |

### Top ten, in order
1. LP-1.1 the draft fix · 2. LP-1.2 the H1 fit · 3. LP-1.4 the mobile menu · 4. LP-1.3 the CTA border · 5. LP-2.3 the hero rework · 6. LP-2.4 How it works · 7. LP-2.5–2.8 the reorder and merges · 8. LP-2.2 + LP-2.9 the heading tiers and spacing · 9. LP-4.1 the motion pause · 10. LP-2.10 + LP-2.11 accent discipline and the channel motif.

---

## Scorecard (1–10)

Merged from the three research files. Where two researchers scored the same area, the evidence is combined; no score was raised beyond its evidence.

| # | Category | Score | Evidence | Verified? |
|---|---|---|---|---|
| 1 | Visual design | **6.5** | + A coherent tokenised paper/night system, honest scenes, restrained shadows. − The broken draft, the H1 under the cards, one H2 size, the 500 closer, the four-paper sag, the placeholder Reel | Observed (screenshots) |
| 2 | Hero effectiveness | **6** | + A clear H1, the CTA above the fold at all six widths, honest facts. − Opens on chaos, 250vh scrub, differentiator and audience in small text, undersized scene | Observed; the "5-second test" is a hypothesis (no user testing) |
| 3 | Layout and spacing | **5.5** | + No horizontal overflow anywhere. − Nine ad-hoc gaps, 272 px between same-colour bands, an inline override, 3–4-line H2s, empty sticky frames | Observed + Code |
| 4 | Brand differentiation | **6.5** | + Apart from the gradient/badge competitors, honest by design. − The paper + Geist + ink pill look is common; the channel motif is tiny | Observed vs the competitor shots; "common look" is a hypothesis |
| 5 | Responsiveness | **6** | + Phones work, no overflow, good reduced motion. − Tablet gets the phone layout with a 46 px H1; 40 px nav targets; the menu doesn't close on an outside tap; 20k px on phones | Observed |
| 6 | Conversion potential | **5.5** | + Low friction, honest pricing, strong grounded-AI proof. − That proof is broken visually; long scrubs; Security late; 15 FAQs; 3 CTAs in the closer | Observed; the conversion effect is a **hypothesis** (no analytics or traffic yet) |
| 7 | Theme and colour | **6** | + Token-only palette with a lint, a strong neutral ramp, almost all text AA. − The draft at 1.1:1, CTA borders 1.22 / 1.90, dimmed lines 3.18 / 2.22, iris overused, three palettes on public pages, the old OG | Measured (contrast script) |
| 8 | Typography | **6** | + Geist variable, preloaded, metrics fallback; bold tight display; good measures. − The H1 overflow, 16 sizes with no tokens, the 500 closer, a flat H1/H2 ratio, 11 px text | Observed + Code |
| 9 | Performance | **8** | + Mobile 94 / desktop 100, CLS 0, no third parties, no images, 7 KB motion. − Mobile LCP 2.95 s (hydration); Sentry on production unmeasured; unbatched reads | Measured (local prod build). **Not verified on production** with Sentry |
| 10 | Accessibility | **7** | + axe 0 on `/`, Lighthouse 100, strong focus, skip link, reduced motion. − **The draft at 1.1:1 (Critical, missed by the tools)**, no motion pause, 1.4.11 border failures, small targets. *The perf-a11y researcher scored 8 before the contrast findings were combined; lowered to 7 here for the Critical contrast failure* | Measured by automation + keyboard; **no screen reader tested** |
| 11 | SEO fundamentals | **8** | + Complete metadata, honest JSON-LD, FAQPage 15/15, `llms.txt`, sitemap. − Old share image, website chat missing, deep pages unlinked, minor heading issues | Observed (served HTML) |
| 12 | Code maintainability | **5** | + A clean server/data/motion split, colours linted. − 574 px literals, 16 radii, 12 night overrides, collision-prone names (one shipped a Critical bug), JS-duplicated breakpoints | Code |

---

## Questions for the owner

1. **Width.** C-074 (UI-076, "pages fill the width") explicitly says "the marketing site keeps its centred layout", so the 1240 px cap is compliant. At 1920 it leaves 340 px of margin each side, and about 660 px at 2560. Keep 1240, or widen the scenes to 1440 (text measures stay in `ch`)? *My default: keep 1240 for now and revisit after the hero rework.*
2. **Scroll-scrubs.** Remove the hero scrub in favour of a one-shot ≤1.2 s sort (recommended), or keep a short one (≤140vh)? And may How it works go from 340vh to about 200vh?
3. **Share image.** OK to redraw `/og.png` on paper with the H1 in Geist 700, and drop the C-129 "stays dark" exception?
4. **Positioning line.** Should the title, description, tagline and `llms.txt` name website chat (and comment-to-DM)? Which single line?
5. **Audience in the hero.** May the hero sub-line say "For small businesses and creators:" (proposal H-2)? And add the "Who it's for" cards?
6. **Strip fact.** What should replace the duplicated "Official Meta APIs"? Is "Website chat on every plan" still true?
7. **FAQ.** OK to show 6–8 questions on the landing and move the rest to a page (the JSON-LD follows)?
8. **Copy proposals.** Approve or reject each: eyebrow H-1, trust row H-4, "Try your own keyword", Modes kicker "AI reply modes", the email as a text line in the closer.
9. **Monospace labels.** OK to use Geist Mono (it ships with Geist) at 12 px for "Example data" and status labels, or stay Geist-only?
