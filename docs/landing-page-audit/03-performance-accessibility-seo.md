# 03 · Performance, accessibility and SEO

**Summary.** Performance is good and was measured on a production build: Lighthouse 94 on mobile and 100 on desktop, CLS 0, no third-party scripts, no images, and 7 KB gzip of landing-specific JS. The one gap is mobile LCP at 2.95 s, which is bound by hydration.

Accessibility automation is clean: axe found 0 violations on `/`, and focus is strong. The real gaps are elsewhere:
- auto-playing motion with no pause (WCAG 2.2.2);
- the draft bug's 1.1:1 text, which Lighthouse can't see;
- weak secondary-button borders;
- a few small targets.

SEO basics are 8/10. The share image and website chat being missing from the metadata are the main gaps.

**The audit set:** [01 Current state](01-current-state-audit.md) · [02 Visual design](02-visual-design-recommendations.md) · 03 Performance, accessibility and SEO (this file) · [04 Redesign proposal](04-redesign-proposal.md) · [05 Action plan](05-prioritized-action-plan.md) · [06 Design tokens](06-design-token-proposal.md)

Labels: **[Measured]**, **[Observed]**, **[Code]**, **[Hypothesis]**. Paths are relative to `apps/web/src/`.

---

## 1. Measured results

### Method
- **Build:** `NEXT_OUTPUT=standalone pnpm build` of the audit worktree (Next 16.4.2, Turbopack), run with `node server.js` on port 3155. Split hosts mirror production. Clerk dev keys were set in the process environment only.
- **Lighthouse:** 12.8.2, bundled Chromium 1243, default mobile (simulated Slow 4G, 4x CPU) and desktop presets. Three runs per form factor, medians reported. This is a noisy Windows laptop; C-152 notes a single run can swing 20 points.
- **"Before":** production amplychat.com (old dark design), one run, over the real network. A different environment, so compare directionally.
- **What isn't included:** Sentry (no DSN locally) and the VM's sharp (irrelevant: no raster images on `/`).

### Lighthouse on `/` [Measured]
| | Mobile runs | **Mobile median** | Desktop runs | **Desktop median** | Before: prod mobile / desktop |
|---|---|---|---|---|---|
| Performance | 87 / 94 / 94 | **94** | 100 ×3 | **100** | 90 / 98 |
| LCP | 3025 / 2952 / 2953 ms | **2,953 ms** | 666 / 659 / 671 | **666 ms** | 2,692 / 784 ms |
| CLS | 0 | **0** | 0 | **0** | 0 / 0 |
| TBT | 301 / 112 / 112 ms | **112 ms** | 3 / 0 / 15 | **3 ms** | 226 / 0 ms |
| Speed Index | 1844 / 1555 / 1554 ms | **1,555 ms** | 606 / 594 / 605 | **605 ms** | 3,747 / 1,300 ms |
| FCP | 1413 / 1402 / 1401 ms | **1,402 ms** | 351 / 344 / 344 | **344 ms** | 1,479 / 559 ms |
| A11y / BP / SEO | 100 / 100 / 100 | | 100 / 100 / 100 | | 100 / 100 / 100 |

The LCP element is the hero `<h1>` (text). Page weight is 294 KiB, with 1,141 DOM elements on mobile (production: 376 KiB and 1,652 elements).

### Other pages, one run each [Measured]
| | /pricing mobile / desktop | /for-creators mobile / desktop |
|---|---|---|
| Performance | 94 / 100 | 95 / 100 |
| LCP | 2,844 / 606 ms | 2,849 / 599 ms |
| Accessibility | **98 / 98** (heading order) | 100 / 100 |

### What ships to `/` [Measured]
| Chunk | Gzip | What it is |
|---|---|---|
| react-dom | 65 KB | Framework |
| Next runtime and router | 36 KB | Framework |
| Sentry route manifest and glue | 9.6 KB | Lists every `/w/:slug/...` route |
| Next/React internals, `SignedInSwitch` | 8.3 + 7.8 + 8.8 KB | Framework |
| **Two near-identical `MobileMenu` chunks** | 5.4 + 5.3 KB | Duplicate |
| Sentry loader | 3.6 KB | Low-priority preload |
| Landing motion (idle-loaded) | 7 KB | `landing-motion.ts` + `data.ts` |
| CSS | 28 KB (globals + Tailwind) + 7 KB (`site.css`) | Render-blocking; Lighthouse reports 0 ms savings |
| Font | 29 KB | One Geist woff2 |

- Modern-browser JS on first load is about 160 KB gzip (the 39 KB `noModule` polyfill isn't downloaded by modern browsers).
- No Clerk code and no app code leak into `/`.
- Main-thread work on mobile is 2.9 s (simulated), dominated by react-dom (341 ms) and a 336 ms parse/hydrate long task.

### Runtime [Measured]
- **Scroll:** in a full-page scroll at 4x CPU, frames were p50 17 ms, p95 28 ms and max 80 ms on desktop (3 of 378 over 50 ms), and 0 of 487 over 50 ms at 375 px.
- **Interactions** (Event Timing at 4x CPU, headless):
  - mode switch 64–72 ms;
  - keyword typing 16–88 ms;
  - FAQ toggle 40 and **192 ms** (96 ms input delay on the first click);
  - menu toggle 48–64 ms.
  - All are under the 200 ms INP "good" line, but one is close.

---

## 2. Performance risks and hypotheses

Each is labelled, with how to verify it.

| # | Risk | Label | How to verify |
|---|---|---|---|
| R-1 | **Sentry's lazy SDK chunk (145 KB gzip, including Replay code the app says it doesn't use) loads after idle on production public pages**, where the DSN is set. That would add TBT and compete with the motion chunk. Production mobile TBT is 226 ms against 112 ms locally, which is consistent with this but doesn't prove it | Hypothesis | Lighthouse on amplychat.com and check the network tab for the chunk. Then check `withSentryConfig` `bundleSizeOptimizations` (`excludeReplayIframe/Shadow/Worker`) |
| R-2 | **Mobile LCP 2.95 s is gated by hydration**, not the font. FCP and LCP are the same `<h1>`, painted about 1.5 s apart | Hypothesis (C-152 saw the same) | Lighthouse with `--blocked-url-patterns=_next/static/chunks/*.js`; C-152 got LCP 2.3 s that way |
| R-3 | **Interleaved layout reads and writes in `decideScene.render`**: it toggles a class on each `.line`, then reads `offsetTop` on the next. Also, `hero.render` writes styles before `scrubProgress(decide)` reads a rect, once per frame. It's fine on this machine; it may jank on slow phones | Code; Measured as OK | DevTools Performance at 4x/6x CPU on a mid-range Android; look for "Forced reflow" |
| R-4 | **`layout()` runs on every `resize`** without debouncing, and does forced layouts across 9 notes | Code | Record a window drag-resize in DevTools |
| R-5 | **INP in the first 2–3 s** may suffer while hydration, the motion chunk and (on production) Sentry all compete. The 192 ms FAQ toggle shows the shape | Hypothesis | DevTools at 4x CPU, clicking FAQ and the mode switch in the first 3 s. Once there's traffic: CrUX or Search Console, or `web-vitals` attribution |
| R-6 | **11 infinite CSS animations plus `will-change`** keep compositor work alive while the hero is visible | Hypothesis | DevTools Rendering → "Frame rendering stats" on a low-end device |

## 3. Ranked performance actions

| Rank | ID | Action | Impact | Effort | Confidence |
|---|---|---|---|---|---|
| 1 | P-1 | Measure R-1 on production; if confirmed, drop Replay from the bundle or delay Sentry until after first interaction | Medium (mobile TBT, about 145 KB) | S | Medium |
| 2 | P-4 | Stop infinite animations and the comment timer when off screen or after about 5 s. This also fixes A-1 | Low perf, fixes a11y | S | High |
| 3 | P-2 | `decideScene`: cache `offsetTop` and rects in `layout()`, read both scenes' progress before any writes, batch class toggles, rAF-debounce `resize` | Low now; protects INP on slow phones | S | High |
| 4 | P-7 | Shorter scrubs and fewer scene frames (from 02) reduce scroll work. The redesign's one-shot hero removes the hero rAF work entirely | Low–Medium | (part of the hero task) | Medium |
| 5 | P-3 | Fold the two `MobileMenu` chunks into one | Low (about 5 KB) | S–M | Medium |
| 6 | P-5 | Reduce the hydrated DOM further (Features, the two hero diagrams). This is the only lever left on mobile LCP. Merging Features + Integrations and trimming the FAQ (02) help here as a side effect | Medium on LCP | L | Medium |
| – | P-6 | `content-visibility: auto` | Skip: it was tried in C-155 and broke axe's hit test | – | – |

Not worth doing now: image work (there are none), font subsetting (one 29 KB file), CDN or third-party work (none) and more code splitting.

---

## 4. Accessibility (WCAG 2.2 AA)

### What was and wasn't tested
- **Tested:**
  - axe-core 4.13 (`@axe-core/playwright`), tags wcag2a/aa, wcag21a/aa, wcag22aa and best-practice, on `/` (375 and 1280), `/pricing`, `/for-creators` and `/privacy`;
  - a manual keyboard pass in Chromium;
  - a computed-contrast script over every text and background pair;
  - reflow at 320 px;
  - an emulated reduced-motion pass.
- **Not tested:** screen readers (NVDA, VoiceOver, TalkBack), real touch devices, 200% text spacing, 400% zoom beyond the 320 px width check, Windows high-contrast mode, voice control, and pages other than those five. **This is not a compliance claim**; automated tools catch only part of WCAG.

### axe results [Measured]
| Page | Width | Violations | Needs review |
|---|---|---|---|
| `/` | 375 | 0 | 4 contrast nodes (panel header). Computed by hand: 5.0–5.4:1, pass |
| `/` | 1280 | 0 | 22 contrast nodes (`.note .app` in the moving hero). Static state passes |
| `/pricing` | 1280, 375 | **1: heading-order** (moderate) | 0 |
| `/for-creators`, `/privacy` | – | 0 | 0 |

**axe and Lighthouse both miss the worst issue**, because neither scrolls into the How it works scene: the draft text is about 1.1:1 [Measured in the DOM].

### Findings by severity
| Severity | ID | Finding | WCAG | Label | Fix |
|---|---|---|---|---|---|
| **Critical** | A-0 | AI draft text ≈1.1:1 and broken layout while the scene plays (the `.typing` collision) | 1.4.3 Contrast (AA) | Measured + Code | Rename `.typing` for the DM dots |
| **Medium** | A-1 | No way to pause, stop or hide auto-playing motion over 5 s: hero bob (infinite), comment feed (1.9 s timer), phone loops (9 s, 16 s), closer rows (6 s). Reduced-motion users are protected; others aren't | 2.2.2 Pause, Stop, Hide (A) | Code + Observed | Every loop runs once, or stops when off screen or after about 5 s; or add a small "Pause motion" control |
| **Medium** | A-9 | Secondary button borders 1.22:1 (paper) and 1.90:1 (night) | 1.4.11 Non-text contrast (AA) | Measured | #82848B / #6A6C76 |
| **Medium** | A-10 | Knowledge lines dimmed to 3.18:1 and 2.22:1 during the whole scrub | 1.4.3 (AA) | Measured | Dim to night-ink-3 (5.52:1) instead of opacity |
| **Low–Medium** | A-2 | `/pricing`: `<h1 class="h2">` then `<h3 id="plan-free">`, with no H2 | 1.3.1 (best practice) | Measured | Plan titles as H2 on `/pricing`, or a visually hidden H2 "Plans" |
| **Low** | A-3 | Standalone links under 24 px tall: "Compare every plan limit" (19 px), footer email (18 px) | 2.5.8 Target size (AA) | Measured | `display: inline-block; min-height: 24px` (44 px preferred on touch) |
| **Low** | A-11 | Header CTAs (40 px) and footer links (32 px) are under 44 px on touch. This passes 2.5.8 (24 px) but is below good practice | 2.5.8 (passes) | Measured | 44 px at ≤900 |
| **Low** | A-4 | Two `nav` landmarks named "Main" (header and mobile menu) | 1.3.1 / 2.4.1 (best practice) | Observed | Name the menu's nav "Mobile menu" |
| **Low** | A-5 | The mobile menu stays open when focus Tabs out; an outside tap doesn't close it | 2.4.3 (a disclosure, so not a failure) | Observed + Code | Close on `focusout` and outside `pointerdown` |
| **Low** | A-6 | Logo SVGs lack `aria-hidden` (next to the text "Amplychat") | 1.1.1 (best practice) | Code | `aria-hidden="true"` |
| **Low** | A-12 | Mode switch accessible name "AutoPro" (badge text concatenated) | 2.5.3 Label in name / 4.1.2 | Observed | `aria-label=", Pro plan"` on the badge, or a hidden separator |
| **Low** | A-13 | Graphic marks under 3:1 (comment pink 2.47, wait-mark 2.62, iris-mist 1.92, IG on night 2.52–2.89, web on night 2.78); all labelled with text | 1.4.11 | Measured | Values in [06](06-design-token-proposal.md) |
| **Low** | A-7 | FAQ `<h3>` inside `<summary>`; some screen readers drop the heading role | 4.1.2 (robustness) | Hypothesis | Verify with NVDA and VoiceOver first |
| **Low** | A-14 | 11 px text (`.pro`, `.pl`) | 1.4.4 (good practice) | Code | 12 px minimum |
| **Info** | A-8 | Contrast of text inside the moving hero notes can't be proven by axe (5.0–5.4:1 in the static state) | 1.4.3 | Measured | A fixed text colour per note background keeps it provable |

### What passes [Measured / Observed]
- Focus ring: 2 px solid, offset 3 px. Iris on paper is 5.8–6.8:1 and iris-night on night is 8.3:1. The `.night` override applies on every night band.
- Skip link: the first Tab stop, visible, targets `#main`.
- No keyboard trap. DOM order matches visual order.
- The menu: Escape closes it and returns focus to the button. `aria-expanded` and the label switch correctly.
- Every control has a name. Status dots carry text labels (colour isn't the only signal).
- The mode switch uses `aria-pressed` with a polite live region.
- Reflow at 320 px has no horizontal scroll. `lang="en"` is set.
- Reduced motion: scenes are still, complete and meaningful.

---

## 5. SEO

### Technical issues (kept separate from content)
| Item | Finding | Label | Severity | Fix |
|---|---|---|---|---|
| Share image | `/og.png` is the **old dark "Midnight" card** (`components/marketing/og.tsx`; exception C-129 in `styles/colour-exceptions.ts:93`), with a regular-weight headline and IG/WA dots only | Observed | Medium (brand, share CTR) | Redraw on paper: "Every DM. Every comment. One inbox." in Geist 700, with "One inbox." in iris. Satori supports a 700 Geist file. Drop the exception |
| Canonical | `https://amplychat.com` without a slash; the sitemap and JSON-LD use `/` | Observed | Low | Align on one form |
| Footer headings | Five footer column titles are H2s ("Compare", "Legal and trust" …), inflating the outline | Observed | Low | `<p>` titles, plus one `sr-only` H2 "Site links" |
| FAQ headings | `<h3>` inside `<summary>` | Code | Low | See A-7 |
| Scene H3s | "Price list", "Delivery FAQ" are example-UI labels, not content headings | Code | Low | Make them `<p>` |
| Example data in snippets | Scene text ("Indigo Lane", "$39", "Toronto") is server-rendered and indexable | Hypothesis | Low | `data-nosnippet` on scene containers |
| Section ids | `automations`, `modes` and `security` are hardcoded strings, not in `SECTION_IDS` | Code | Low | Add them to `SECTION_IDS` (the e2e spec reads these ids) |
| Already good | Title (47 chars), description (about 147), OG/Twitter complete, robots, sitemap with real lastmod, honest JSON-LD (offers only when Pro is on sale), FAQPage matching the visible FAQ 15/15, `lang`, descriptive link text, an excellent `llms.txt` | Observed | – | Keep. Note: Google limits FAQ rich results to government and health sites, so FAQPage helps answer engines, not SERP features |

### Content opportunities
1. **Website chat is missing from every metadata line.** The hero, strip and integrations say "Instagram, WhatsApp and your website". The title, description, `SITE_TAGLINE`, the root layout's default description, the footer "about" line, the OG image and `llms.txt` all say Instagram and WhatsApp only. Pick one positioning line and use it everywhere. A description proposal that reuses existing words (**owner to confirm**): "One AI inbox for Instagram DMs and comments, WhatsApp and your website chat. Replies from your own knowledge, plus comment-to-DM automations." (about 140 chars).
2. **"Comment-to-DM" isn't in the title or description**, although it is the most-searched competitor feature and has its own guide.
3. **Deep pages are linked only from the footer.** Link Features items to `/features/ai-inbox`, `/features/comment-intelligence` and `/features/publishing`; Automations to the comment-to-DM guide; Integrations to the WhatsApp API guide; and add the "Who it's for" cards to `/for-creators` and `/for-businesses`.
4. **Kickers can carry intent terms** without changing the H2s. For example, "Instagram comment-to-DM automations" above "Comment LINK, get the link in a DM".
5. **Make the share image copy match the H1.**
6. **Add `sameAs` and `twitter:site`** once real profiles exist. It's already wired through `SOCIAL_PROFILES`.
