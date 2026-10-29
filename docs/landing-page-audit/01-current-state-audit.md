# 01 · Current state audit: the Amplychat landing page

**Summary.** This is an inventory of the new paper-and-night landing page (branch `feature/site-redesign`, PR #178, C-155 and C-156) as of 2026-10-30. The system underneath is sound. Colours are fully tokenised and there is only one small motion island. The measured scores are strong: Lighthouse mobile 94 and desktop 100. Two bugs undercut it, though. The "AI draft" in How it works renders as an unreadable white box whenever motion is on, and the hero headline runs under the scene at 1440 px and wider. Beyond those, the main problems are a long scroll-scrub hero, a sag in the middle of the page (four paper sections in a row), and no type, spacing or radius scale.

**The audit set:** 01 current state (this file) · [02 Visual design](02-visual-design-recommendations.md) · [03 Performance, accessibility and SEO](03-performance-accessibility-seo.md) · [04 Redesign proposal](04-redesign-proposal.md) · [05 Action plan](05-prioritized-action-plan.md) · [06 Design tokens](06-design-token-proposal.md)

**Evidence labels** used in all six docs:
- **[Observed]**: seen in a screenshot or measured in the rendered page.
- **[Measured]**: a Lighthouse, axe or timing number.
- **[Code]**: read in the source.
- **[Hypothesis]**: a judgement or inference that hasn't been verified.

**How it was gathered:**
- **Visual:** Playwright Chromium at 375, 430, 768, 1366, 1440 and 1920 px against the owner's dev server. The dev-mode "N" badge appears bottom-left in every screenshot; ignore it.
- **Performance:** Lighthouse 12.8.2 against a local production standalone build.
- **Accessibility:** axe-core 4.13 and a manual keyboard pass.
- **Code:** read in the `audit` worktree.

All file paths are relative to `apps/web/src/` unless stated otherwise.

---

## 1. Stack, routes, layouts and components

### Stack [Code]
| Piece | What it is |
|---|---|
| Framework | Next.js 16.4.2 (App Router, Turbopack build); the landing uses ISR (`revalidate = 3600`, `app/(marketing)/page.tsx`) |
| Styling | Tailwind v4, CSS-first (`styles/globals.css` `@theme`), plus a hand-written site stylesheet `components/site/site.css` (504 lines) |
| Fonts | Geist variable through `next/font` (`app/layout.tsx:15-18`) |
| Motion | No animation library. There is one client island, `LandingMotion.tsx`, which dynamic-imports `landing-motion.ts` (554 lines) after `load` and idle |
| Auth | Clerk wraps every page via `RootAuth`, but no Clerk code ships to `/`; `SignedInSwitch` reads the `__client_uat` cookie hint instead (C-148) [Measured: no `clerk` string in any landing chunk] |
| Monitoring | Sentry client glue ships in the first load. The full SDK chunk loads lazily on public pages only when `NEXT_PUBLIC_SENTRY_DSN` is set |

### Routes and layouts [Code]
| File | Role |
|---|---|
| `app/layout.tsx` | Root layout: fonts, the theme init script (`data-theme="dark"` default), `RootAuth`, default metadata (`%s · Amplychat`) |
| `app/(marketing)/layout.tsx` | Imports `site.css`. Wraps pages in `<div class="site …">` with `ThemePin`, a skip link, `SiteHeader`, the children and `SiteFooter`. Sets the OG and Twitter defaults and `themeColor` #F5F5F2 |
| `app/(marketing)/page.tsx` | The landing page: `JsonLd`, 11 sections, then `LandingMotion` |
| About 30 other marketing routes | compare/*, features/*, for-creators, for-businesses, guides/[slug], legal pages. Built from `InfoPage`, `GtmPageView`, `SolutionPageView` and `GuideView` |
| Metadata routes | `app/robots.ts`, `app/sitemap.ts`, `app/llms.txt/route.ts`, `app/(marketing)/og.png/route.tsx` (draws `components/marketing/og.tsx`), the manifest and the icons |

### Components [Code]
- **Landing sections** (`components/marketing/landing/`): `Hero`, `Strip`, `Decide`, `Comments`, `Modes`, `Features`, `Channels`, `Trust`, plus `data.ts` (example data), `copy.ts` (the H1 and hero line), `LandingMotion.tsx` and `landing-motion.ts`.
- **Shared marketing pieces** (`components/marketing/`): `SiteHeader`, `MobileMenu`, `HeaderAuth`, `SiteFooter`, `Faq`, `FinalCta`, `Pricing`, `PlanMatrix`, `JsonLd`, `og.tsx`.
- **`primitives.tsx`**: `LogoMark`, `Logo`, `CtaLink`/`ctaClass`, `SectionHeading`, `Container`, and the class-name constants `PAGE_HEADING`, `SECTION_TITLE`, `BAND_TITLE` and `SECTION_EYEBROW`.
- **Left over from the previous design:** `classes.ts` (`MARKETING_CARD*`, Tailwind glass cards), and app `ui/button`, `ui/card` and `ui/badge` on some inner public pages (data-deletion, unsubscribe). These are a second visual language on the public site.
- **Content data** (`lib/marketing/`): `site.ts` (name, taglines, nav), `seo.ts` (metadata and JSON-LD), `faq.ts` (15 Q&As, shared by the page and the FAQPage JSON-LD), `plans.ts`, `llms.ts`.

## 2. Styling system, tokens and theme [Code]

The system has four layers:
1. **Raw palette in `@theme`** (`globals.css:155-193`): `--color-paper`, `--color-ink*`, `--color-iris*`, `--color-night*`, source colours, status colours and avatars. `--color-*: initial` locks the palette (`globals.css:42`).
2. **Short aliases on `.site`** (`globals.css:504-535`): `--paper`, `--ink-2`, `--iris-night`, `--rule`, plus `color-mix` shades and three shadows. `site.css` uses only these.
3. **App tokens re-pointed inside `.site` and `.site .night`** (`globals.css:537-584`), so app components on public pages wear the site palette. Gaps: `--color-brand-deep` and `--gradient-brand` are not re-pointed, and on night bands `--color-brand-strong` stays #4B3FE0.
4. **`site.css`**: every rule sits in `@layer components { .site { … } }`. The design lint (`styles/design-lint.test.ts`) refuses colour literals there. The lint holds: there are no hex values in `site.css`.

### Core palette in use
| Role | Token | Value |
|---|---|---|
| Page (paper) | `--paper` | #F5F5F2 |
| Alt band | `--paper-2` | #EDEDE9 |
| Card (sheet) | `--sheet` | #FFFFFF |
| Text 1 / 2 / 3 | `--ink`, `--ink-2`, `--ink-3` | #121317 / #464953 / #686B74 |
| Hairline | `--rule`, `--rule-2` | #DFDFDA / #EAEAE6 |
| Night bg / raised / high | `--night`, `--night-2`, `--night-3` | #0F1017 / #181923 / #232532 |
| Night text 1 / 2 / 3 | night-ink | #F2F2F5 / #B7B8C4 / #8E909E |
| Accent | `--iris`, `--iris-ink`, `--iris-soft`, `--iris-night` | #4B3FE0 / #3A2FC2 / #ECEAFD / #A8A1FF |
| Sources | `--ig`, `--cm`, `--wa`, `--web` | #BE185D / #E07FA8 / #16A34A / #0F766E |
| Status | ok / wait / stop | #1C7343 / #985200 / #A43535 |

**Theme.** The public site is always light (paper), with "night" bands as sections. `ThemePin` holds the theme, and `themeColor` is paper. The 12 `.night …` overrides in `site.css` (lines 34, 48, 55, 57, 72-77, 393-394 and 409) re-colour components for night bands one by one, instead of re-pointing aliases.

**What isn't tokenised:**
- Type, spacing, radii, durations and breakpoints. `site.css` has 574 px literals (62 distinct values), 16 radii and 9 durations.
- Breakpoints: 520, 900/901 and 1060 px. The 901 px breakpoint is duplicated in JS in `SiteHeader.tsx:11` and `landing-motion.ts:38`.

## 3. Fonts [Code + Observed]
- **Geist**, the variable font (`wght` 100–900). One latin woff2 (29 KB) is preloaded, with `font-display: swap`. There is a generated metrics fallback ("Geist Fallback" = Arial with `size-adjust: 104.76%`), which keeps CLS at 0.
- **Geist Mono** has `preload: false` and isn't used on the landing page.
- **Weights in use** [Observed]: 400 (274 elements), 500 (24), 600 (151) and 700 (20). Headings are 700, except the closing H2, which is **500** (`site.css:391`).
- There is a conflict on record: `globals.css:455-456` says "weights are 400, 500 and 600 only" (C-070), while the site uses 700 by owner decision (C-155). Nothing exempts the site, so a future lint pass could "fix" the headings.

## 4. Section order and purpose [Code: `app/(marketing)/page.tsx:39-49`; heights Observed at 1440 px]

| # | Section (component) | Band | Purpose | Height at 1440 |
|---|---|---|---|---|
| 1 | Hero (`Hero.tsx`) | paper | Promise "Every DM. Every comment. One inbox.", two CTAs and two trust facts. A 250vh scroll-scrub turns a scattered pile of messages into a sorted inbox | 2,250 px |
| 2 | Strip (`Strip.tsx`) | sheet (white) | Four true facts: 1 inbox, 2,000 AI credits, N automations, Official Meta APIs | 133 px |
| 3 | How it works (`Decide.tsx`) | night | The differentiator: AI replies from your own knowledge, with citations, and hands off when unsure. A 340vh scrub | 3,487 px |
| 4 | Automations (`Comments.tsx`) | paper | Creator use case: comment LINK, get the link in a DM. Live keyword input | 1,143 px |
| 5 | Modes + setup steps (`Modes.tsx`) | paper-2 | Off / Suggest / Auto switch, then "Set up in three steps" | 1,260 px |
| 6 | Features (`Features.tsx`) | paper | Nine further features with honest statuses | 1,180 px |
| 7 | Integrations (`Channels.tsx`) | paper | Honest status per channel (live / waiting for Meta / your own) | 1,171 px |
| 8 | Security (`Trust.tsx`) | night | Five true safety statements and a privacy link | 1,010 px |
| 9 | Pricing (`Pricing.tsx`) | paper | Free and Pro. Pro is "coming soon" in production; Free becomes the primary card when Pro isn't on sale (`Pricing.tsx:137`) | 1,726 px |
| 10 | FAQ (`Faq.tsx`) | paper-2 | 15 questions in native `<details>` | 1,453 px |
| 11 | Closing CTA (`FinalCta.tsx`) | night | Final action, a mini inbox, perks | 764 px |
| – | Footer (`SiteFooter.tsx`) | night | Five link columns (30 links), the "not affiliated with Meta" line | – |

The document is **16,255 px tall at 1440** and **20,278 px at 375** [Observed].

Screenshot: [full page at 1440](shots/section-rhythm-1440-full.png). Sections 4–7 are four light bands in a row, about 4,700 px with no night band.

## 5. Motion islands [Code + Measured]

| Motion | Where | Behaviour | Under reduced motion |
|---|---|---|---|
| Hero scrub | `site.css:131`, `landing-motion.ts` | 250vh sticky; the pile sorts into the inbox as you scroll (desktop ≥901 px) | Static sorted inbox |
| Hero idle "bob" | `site-bob` keyframes | Infinite, 4.2–6.3 s per note | Off |
| Phone hero loop | `landing-motion.ts:69-75` | A 9 s sort / hold / unsort loop, endless | Off |
| How it works scrub | `site.css:181-205` | 340vh sticky: scan, wires, word-by-word typing | Complete end state |
| Phone How it works loop | `landing-motion.ts` | 16 s loop | Off |
| Comments stream | `landing-motion.ts` `comments()` | `setInterval(1900ms)` while on screen (IntersectionObserver) | Off |
| Mode swap | `Modes.tsx` + script | 450 ms | Works (instant) |
| Closing mini inbox | `.falling` | 6 s infinite loop | Off |

**How it loads** [Code]: `LandingMotion.tsx` (1.3 KB) waits for `load`, then `requestIdleCallback` (800 ms timeout), then imports a 7 KB gzip chunk. The server markup is complete without it. The script animates only transforms, opacity, classes and custom properties.

**Measured:** in a full-page scroll at 4x CPU, frames were p50 17 ms and p95 28 ms, with 3 of 378 frames over 50 ms on desktop.

## 6. Metadata [Observed in served HTML; Code in `lib/marketing/seo.ts`, `site.ts`]
| Item | Value |
|---|---|
| Title | "Amplychat · AI inbox for Instagram and WhatsApp" (47 chars) |
| Description | "Instagram DMs, comments and WhatsApp in one inbox for businesses and creators. AI replies from your own knowledge, plus comment and DM automations." |
| Canonical | `https://amplychat.com` (no trailing slash; the sitemap and JSON-LD use `/`) |
| OG / Twitter | Complete; 1200×630 `og.png`. **The image is the old dark "Midnight" card** (`og.tsx`, exception C-129) |
| JSON-LD | Organization, WebSite, SoftwareApplication (offers only when Pro is on sale), and FAQPage (15/15 questions match the visible FAQ) |
| robots / sitemap / llms.txt | Present and correct |
| theme-color | #F5F5F2 |

## 7. Measured baseline

**Method** [Measured]:
- Lighthouse 12.8.2, default mobile and desktop presets, 3 runs each, medians shown.
- **After** (the new design) is a local production standalone build (`node server.js`) on a Windows laptop.
- **Before** (the old dark design) is production amplychat.com from the same machine, 1 run.
- The environments differ (no TLS or CDN locally), so compare directionally.

| Metric | Before: production, old design (mobile / desktop) | After: new design, local prod build (mobile / desktop, median of 3) |
|---|---|---|
| Performance | 90 / 98 | **94 / 100** |
| LCP | 2,692 ms / 784 ms | 2,953 ms / 666 ms |
| CLS | 0 / 0 | 0 / 0 |
| TBT | 226 ms / 0 ms | 112 ms / 3 ms |
| Speed Index | 3,747 ms / 1,300 ms | **1,555 ms** / 605 ms |
| FCP | 1,479 ms / 559 ms | 1,402 ms / 344 ms |
| Accessibility / Best practices / SEO | 100 / 100 / 100 | 100 / 100 / 100 |
| Transferred | 376 KiB / 393 KiB | 294 KiB |
| DOM elements | 1,652 | 1,141–1,150 |

Notes:
- The first mobile run was 87 (TBT 301 ms), a cold-server artefact; runs 2 and 3 were identical.
- The LCP element is the hero `<h1>` (text) on both form factors.
- **Lighthouse a11y 100 doesn't see the draft bug**, because Lighthouse doesn't scroll into the scene. The bug is real and measured at about 1.1:1 contrast (see below).

## 8. Major issues

Severity: Critical, High, Medium or Low. Effort: S (hours), M (a day or two) or L (more).

| # | Issue | Evidence | Severity | Impact | Confidence | Effort | Action |
|---|---|---|---|---|---|---|---|
| 1 | **The AI draft renders as a broken light box while the How it works scene plays.** `landing-motion.ts:247` adds `typing` to `p.ddraft-t`; `site.css:280` styles every `.typing` as the DM "typing dots" bubble (paper-2 background, inline-flex). The text becomes #F2F2F5 on #EDEDE9, about 1.1:1, split into flex columns. At 375 px it overflows the card to x=381 | [Observed + Code] [1440](shots/draft-bug-1440.png), [375](shots/draft-bug-375.png); correct under reduced motion: [shot](shots/draft-reduced-motion-1440.png) | Critical | Brand, conversion, a11y | High | S | Rename the DM indicator class to `.dm-typing` (`site.css:280-283`, `landing-motion.ts:466`). Keep `.ddraft-t.typing` (`site.css:215-216` relies on it) |
| 2 | **The H1 "Every comment." overflows its 508 px column** by 68 px at 1440 and 78 px at 1920+, and runs under the scene notes, because `.h1 .phrase { white-space: nowrap }` (`site.css:136`) and the copy column is 0.9fr (`site.css:133`) | [Observed] [1440](shots/hero-1440.png): the full stop is hidden under the WhatsApp card | High | Brand, UX | High | S | Display size `clamp(2.75rem, 2.193rem + 2.286vw, 4.25rem)` (44→68 px), `.hero-grid` 1fr/1fr above 1060 px, and `.hero-copy { position: relative; z-index: 2 }` |
| 3 | **The hero opens on the scattered pile and is a 250vh scrub.** The sorted inbox (the promise) appears only after scrolling, and nothing else is visible for about 1.5 screens | [Observed] [1440](shots/hero-1440.png) vs [sorted 1920](shots/hero-1920-sorted.png) | High | Conversion, UX | Medium | M | Show the sorted inbox on load; play the sort once (≤1.2 s), or cut the scrub to ≤140vh |
| 4 | **The How it works scrub is 340vh, and its sticky frame has no heading**; it opens on an empty thread with about 400 px of dead space | [Observed] [empty frame](shots/decide-empty-frame-1440.png) | High | UX | High | M | About 200vh; a title row inside the sticky frame; start with the question in the thread; `.thread-b` min-height 380 px |
| 5 | **The rhythm sags: four paper sections in a row** (Automations, Modes, Features, Integrations), about 4,700 px | [Observed] [full page](shots/section-rhythm-1440-full.png) | High | Brand, UX | High | M | Move Security up and merge Integrations into Features (see 02 and 04) |
| 6 | **One H2 size everywhere (58 px)**, with ragged 3–4-line breaks in 560 px split-head columns, and the **closing H2 is weight 500** (`site.css:51, 236, 391`) | [Observed] | Medium | Brand | High | S | Two heading tiers, wider heading column, `max-width` in `ch`, closer at 700 |
| 7 | **No spacing, type or radius scale**: 9 different heading-to-content gaps, 272 px between same-colour bands, an inline `style={{ paddingTop: 40 }}` at `Channels.tsx:85`, 16 radii, 16 font sizes | [Code] | Medium | Maintainability, UX | High | M | Scale tokens in `@theme` (see 06) |
| 8 | **Secondary CTA borders fail 3:1**: 1.22:1 on paper, 1.90:1 on night (WCAG 1.4.11) | [Measured] contrast script | Medium | Conversion, a11y | High | S | Control border #82848B (3.42:1) and #6A6C76 on night (3.63:1) |
| 9 | **Auto-playing motion has no pause** (infinite bob, 1.9 s comment loop, 9 s and 16 s phone loops, 6 s closer loop) (WCAG 2.2.2) | [Code + Observed] | Medium | a11y, UX | Medium | S–M | Every loop runs once or stops after about 5 s or off screen |
| 10 | **Tablet (768 px) gets the phone layout** with the H1 stuck at its 46 px floor and a centred 368 px inbox | [Observed] [768](shots/hero-768.png) | Medium | UX | High | S | Tablet type tier; inbox aligned with the text; nav links from 760 px |
| 11 | **Mobile menu**: an outside tap doesn't close it (`MobileMenu.tsx` only handles Escape [Code, verified]); focus can leave the open panel; no scrim; three "Start free" buttons at once; 40 px header CTAs | [Observed] [menu](shots/mobile-menu-375.png) | Medium | a11y, UX | High | S | Close on outside pointerdown and focusout; drop "Start free" from the menu; 44 px targets |
| 12 | **The share image is the old dark design** (`og.tsx`, C-129 exception) | [Observed] | Medium | Brand | High | S–M | Redraw on paper with the H1 in Geist 700 |
| 13 | **Iris overused** (11+ roles), so it no longer signals "act here" or "AI did this" | [Code + Observed] | Medium | Brand | Medium | S | Reserve iris for links, focus, selection and AI moments |
| 14 | **12 hand-written `.night` overrides**, plus leftover `MARKETING_CARD` and app gradient buttons on public pages | [Code] | Medium | Maintainability | High | M | Semantic aliases re-pointed in `.night`; retire `classes.ts` |
| 15 | **Collision-prone class names** (`.typing`, `.line`, `.rule`, `.close`, `.mi`, `.pl` …) and bare-word state classes; issue 1 is the proof | [Code] | Medium | Maintainability | High | M | `is-*` state classes; rename incrementally |
| 16 | **Width cap 1240 px** (`site.css:38`): 340 px of empty margin each side at 1920 and about 660 px at 2560 | [Observed] [2560](shots/wide-2560.png) | Low | Brand | High | S | **Not a conflict**: C-074 (UI-076) says "the marketing site keeps its centred layout". Widening is an owner choice (see 05, questions) |
| 17 | **Small items**: Reel placeholder icon, grey nav slab over night bands, redundant hero caption, 11 px text, footer H2s, FAQ `<h3>` inside `<summary>`, two navs named "Main", `/pricing` heading order (axe) | Various | Low | Brand, a11y | High | S | See 02 and 03 |

### Corrections made while writing this audit (verified in code)
- **"Pages fill the width" is C-074, not C-076.** C-074 explicitly exempts the marketing site, so the 1240 px cap is compliant. The researchers flagged it as a possible conflict; it isn't one.
- **The inline `paddingTop: 40` is at `Channels.tsx:85`.** The research files gave lines 424 and 446.
- **Pricing already makes Free the primary card when Pro isn't on sale** (`Pricing.tsx:137`: `main = proOnSale ? pro : free`). The visual audit marked this "to be verified"; it is done.
- **The system audit's display-size `clamp()` had a wrong intercept.** `1.86rem + 2.29vw` gives 63 px at 1440, not 68. The corrected value is `2.193rem + 2.286vw`, used throughout these docs.
- **`e2e/landing.spec.ts` asserts the section order**, so any reorder must update that spec in the same change.
