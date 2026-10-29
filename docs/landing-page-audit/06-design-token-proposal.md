# 06 · Design token proposal

**Summary.** These are the actual values for the site's colours, type, spacing, radii, shadows, containers, breakpoints and interactive states. They map onto the existing Tailwind v4 `@theme` in `apps/web/src/styles/globals.css` and the `.site` alias block that `components/site/site.css` reads. There are no new libraries, no build step and no CSS-in-JS. Colours change in only seven places: ink-3 nudged darker, two control-border tokens, and four mark colours. Everything else is giving names (tokens) to values that are hard-coded today.

**The audit set:** [01 Current state](01-current-state-audit.md) · [02 Visual design](02-visual-design-recommendations.md) · [03 Performance, accessibility and SEO](03-performance-accessibility-seo.md) · [04 Redesign proposal](04-redesign-proposal.md) · [05 Action plan](05-prioritized-action-plan.md) · 06 Design tokens (this file)

Labels:
- **[Measured]**: every contrast ratio here was computed with the WCAG 2.x formula and re-checked while writing.
- **[Code]**: current values, read from `globals.css` and `site.css`.
- **Proposed** values are recommendations; they haven't been built.

---

## How it fits (no over-engineering)

1. **Raw values in `@theme`** (`globals.css`), next to the existing `--color-paper`, `--color-ink` and so on. `pnpm tokens` already generates `tokens.generated.ts/json` from this file, and the design lint already reads it.
2. **Short aliases on `.site`** (`globals.css:504-535`), the existing pattern: `--paper`, `--ink-3` and so on. Add semantic aliases (`--s-bg`, `--s-text`, `--s-line-control`, `--s-cta-bg` …) and **re-point them inside `.site .night`**. That replaces the 12 hand-written `.night` overrides in `site.css`.
3. **`site.css` consumes only `var(--…)`**, as it already does for colour. The lint keeps refusing colour literals.
4. **JS reads breakpoints from `tokens.generated.ts`** (the `lib/breakpoints.ts` pattern), not from the literals in `SiteHeader.tsx:11` and `landing-motion.ts:38`.

Don't Tailwind-ify `site.css`, add a token build tool, or create per-component token files.

---

## 1. Colours

### Changed or new [Measured]
| Token (`@theme`) | Alias on `.site` | Current | Recommended | Contrast of recommended | Purpose |
|---|---|---|---|---|---|
| `--color-ink-tertiary` | `--ink-3` | #686B74 (4.87 paper, **4.54** paper-2, **4.50** iris-soft) | **#5E616A** | 5.66 paper · 5.27 paper-2 · 6.19 sheet · 5.23 iris-soft | Meta text; removes the near-misses |
| `--color-line-control-site` (new) | `--line-control` | uses `--rule` #DFDFDA (**1.22** on paper) | **#82848B** | 3.42 paper · 3.18 paper-2 · 3.74 sheet | Secondary button, inputs, outlined controls (WCAG 1.4.11) |
| `--color-night-line-control` (new) | `--night-line-control` | night-line ≈ #414248 (**1.90**) | **#6A6C76** | 3.63 night · 3.34 night-2 | Secondary button on night |
| `--color-ig-night` (new) | `--ig-night` | #BE185D on night (**2.52–2.89**) | **#E0559A** | 4.94 night-2 · 4.29 night-3 | Instagram mark on night |
| `--color-web-night` (new) | `--web-night` | #0F766E on night-3 (**2.78**) | **#2AA597** | 5.01 night-3 | Website-chat mark on night |
| `--color-site-wait-mark` | `--wait-mark` | #D08A22 (**2.62** on paper) | **#B06A00** | 3.92 paper | "Waiting" status dot |
| `--color-iris-mist` | `--iris-mist` | #B9B4F5 (**1.92** on sheet) | **#8A82EB** | 3.24 sheet | Summary bar "other" segment |
| `--color-comment` | `--cm` | #E07FA8 (**2.47** paper, 2.70 sheet) | **Stop using as a mark**: show comments as a hollow 2 px ring in `--ig` #BE185D (6.04 on sheet) | 6.04 | Two pinks within 2.2:1 of each other can't both pass 3:1 and stay distinct |
| `.site .night` `--color-brand-strong` | – | #4B3FE0 (2.79 on night) | Re-point to `--color-iris-night` | 8.32 night | App components on night bands |
| `.site` `--gradient-brand` / `--color-brand-deep` | – | #2B2585 → #4B3FE0 gradient, not re-pointed | Re-point `--gradient-brand` to flat `var(--color-ink)` | 18.56 with white | One CTA look across public pages |

### Kept as is [Measured]
| Role | Token | Value | Key ratios |
|---|---|---|---|
| Page | `--paper` | #F5F5F2 | – |
| Alt band | `--paper-2` | #EDEDE9 | – |
| Surface | `--sheet` | #FFFFFF | – |
| Text 1 | `--ink` | #121317 | 17.00 paper · 18.56 sheet |
| Text 2 | `--ink-2` | #464953 | 8.22 paper · 7.65 paper-2 |
| Hairline (decorative only) | `--rule` / `--rule-2` | #DFDFDA / #EAEAE6 | 1.22 paper: never for controls |
| Accent | `--iris` | #4B3FE0 | 6.23 paper · 5.80 paper-2 · 6.80 with white |
| Accent text on soft fill / CTA hover | `--iris-ink` | #3A2FC2 | 7.51 on iris-soft · 8.88 with white |
| Accent soft fill | `--iris-soft` | #ECEAFD | – |
| Night bg / raised / high | `--night` / `--night-2` / `--night-3` | #0F1017 / #181923 / #232532 | – |
| Night text 1 / 2 / 3 | night-ink | #F2F2F5 / #B7B8C4 / #8E909E | 16.98 / 9.64 / 5.99 on night; 3 = 5.52 on night-2 |
| Accent on night | `--iris-night` | #A8A1FF | 8.32 night |
| Sources on paper | `--ig` / `--wa` / `--web` | #BE185D / #16A34A / #0F766E | 6.04 / 3.30 / 5.47 on sheet |
| Status | ok / wait / stop (+ soft fills) | #1C7343 / #985200 / #A43535 | 5.03 / 5.18 / 5.56 on their soft fills |

### Usage rules
- **Iris** is only for links, focus, selected state, the primary hover and AI moments (drafts, citations, "One inbox.").
- **Kickers, step numbers and feature icons** use `--ink-3` or `--ink`.
- **The dimmed state** in scenes uses `--night-ink-3` (5.52 on night-2), never opacity under .72.

---

## 2. Type

The fluid range runs from 390 to 1440 px. Intercepts were checked by hand; this corrects the research file's display intercept.

| Token | `clamp()` / value | 390 → 1440 px | Weight | Line height | Tracking | Max width | Replaces (current) |
|---|---|---|---|---|---|---|---|
| `--type-display` | `clamp(2.75rem, 2.193rem + 2.286vw, 4.25rem)` | 44 → 68 | 700 | 1.0 | −0.045em | 12ch | `.h1` `clamp(46px, 5.6vw, 82px)` |
| `--type-h1-page` | `clamp(2.25rem, 1.693rem + 2.286vw, 3.75rem)` | 36 → 60 | 700 | 1.04 | −0.04em | 16ch | `.h-page` `clamp(38px, 5vw, 66px)` |
| `--type-h2` | `clamp(2rem, 1.536rem + 1.905vw, 3.25rem)` | 32 → 52 | 700 | 1.06 | −0.035em | 18ch (closer 14ch) | `.h2` 34–58 px; `.close h2` 38–66 px at 500 |
| `--type-h2-sm` | `clamp(1.75rem, 1.471rem + 1.143vw, 2.5rem)` | 28 → 40 | 700 | 1.08 | −0.03em | 20ch | (new utility tier) |
| `--type-h3` | `clamp(1.5rem, 1.314rem + .762vw, 2rem)` | 24 → 32 | 700 | 1.12 | −0.025em | 24ch | `.h-sec` `clamp(26px, 3vw, 36px)` |
| `--type-stat` | `clamp(2.75rem, 2.286rem + 1.905vw, 4rem)` | 44 → 64 | 700 | 1.0 | −0.04em | – | `.price` 64 / 52 px |
| `--type-stat-sm` | `clamp(1.5rem, 1.314rem + .762vw, 2rem)` | 24 → 32 | 700, `tabular-nums` | 1.1 | −0.02em | – | `.strip-in b` 20 px |
| `--type-title` | `1.25rem` | 20 | 600 | 1.25 | −0.015em | – | 20 / 22 px card titles, 4 trackings |
| `--type-lede` | `clamp(1.0625rem, 1.016rem + .19vw, 1.1875rem)` | 17 → 19 | 400 | 1.55 | 0 | 56ch (hero 44ch) | `.lede` 18, `.hero-sub` 19 |
| `--type-body` | `1rem` | 16 | 400 | 1.6 | 0 | 65ch | body; FAQ answers (LH 1.7) |
| `--type-body-sm` | `.9375rem` (= existing `--text-md`) | 15 | 400; buttons 600 | 1.55 | 0 | 60ch | card bodies, buttons, nav |
| `--type-label` | `.875rem` | 14 | 400; kicker 500 | 1.5 | kicker +0.01em | – | kicker, facts, footer |
| `--type-caption` | `.8125rem` | 13 | 400 | 1.45 | 0 | – | captions, legends |
| `--type-micro` | `.75rem` (**minimum**) | 12 | 600 / 400 | 1.35 | +0.01em | – | tags, chips; **raises 11 px** `.pro`, `.pl` |

The result is 14 steps instead of 16 ad-hoc sizes, 7 line-heights instead of 16, and 6 trackings instead of 12. The font stays Geist. Add a comment at `globals.css:455` that `.site` uses 700 for display (C-155).

---

## 3. Spacing

A 4 px grid plus three fluid rhythm tokens.

| Token | Value | Use |
|---|---|---|
| `--space-1` … `--space-16` | 4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64 px (`--space-1, -2, -3, -4, -5, -6, -8, -10, -12, -14, -16`) | Component internals. Retire the off-grid 5, 7, 9, 11, 13, 18, 22, 26 and 30 px over time |
| `--space-section` | `clamp(72px, 6vw + 40px, 128px)` | `.sec`, `.close`, `.decide-head` (today 136 / 128 / 88) |
| `--space-section-tight` | `clamp(48px, 4vw + 24px, 88px)` | Top padding when two same-colour bands touch (today 272 px combined) |
| `--space-head` | `clamp(32px, 2.5vw + 16px, 56px)` | Heading block → content (today 40 / 56 / 64 / 72) |
| `--space-band` | `clamp(56px, 48px + 1.5vw, 72px)` | `.band`, `.page-head` bottom on inner pages |
| `--gutter-site` | `clamp(16px, 3vw + 4px, 64px)` | `.wrap` side padding (today 32 / 16) |

---

## 4. Radii

Five steps instead of 16. They're close to today's most-used values, so the change is barely visible.

| Token | Value | Use (today's values folded in) |
|---|---|---|
| `--radius-site-xs` | 6px | Tags, chips, citations, the Reel label (5, 6) |
| `--radius-site-sm` | 10px | Nav buttons, inputs, menu items, switch segments, icon tiles (8, 9, 10) |
| `--radius-site-md` | 12px | Buttons, notes, hand-off, bubbles (12, 14, 16) |
| `--radius-site-lg` | 18px | Cards, panels, tables, post, rule, thread, mini (18, 20) |
| `--radius-site-xl` | 22px | Plan cards, the phone-like DM frame (22) |
| (literals allowed) | 50% · 999px | Avatars and dots · pills |

---

## 5. Shadows

Keep them. Restraint is a strength [Observed].

| Token | Value | Use |
|---|---|---|
| `--shadow-panel` | `0 1px 2px ink/4%, 0 40px 80px -40px ink/35%` | Hero inbox |
| `--shadow-note` | `0 22px 40px -18px ink/42%, 0 2px 6px ink/6%` | Notes (if any remain in motion) |
| `--shadow-token` | `0 8px 20px -8px iris/70%` | The flying "DM" token |
| `--shadow-nav` (new) | `0 1px 0 var(--rule-2), 0 8px 24px -16px rgb(18 19 23 / .18)` | Header after scroll |

---

## 6. Containers

| Token | Value | Notes |
|---|---|---|
| `--container-site` | **1240px** (current) | Allowed by C-074 ("the marketing site keeps its centred layout"). Owner option: 1440px for wider scenes (question 1 in [05](05-prioritized-action-plan.md#questions-for-the-owner)) |
| `.wrap` | `max-width: calc(var(--container-site) + 2 * var(--gutter-site)); padding-inline: max(var(--gutter-site), env(safe-area-inset-left))` | |
| `--measure-hero` | 44ch | Hero sub-line |
| `--measure-lede` | 56ch | Ledes |
| `--measure-body` | 65ch | Body, FAQ answers |
| `--hero-max-h` | 860px | Hero height `min(100svh - 64px, var(--hero-max-h))` |
| `--nav-h` | 64px | Already on `.site`. Fix `landing-motion.ts:39`, which reads it from `<html>` (empty, so it always falls back to 64) |

---

## 7. Breakpoints

Today the site uses 520, 900/901 and 1060 px, and inner pages also use Tailwind's md / lg / xl.

| Token | Value | Use |
|---|---|---|
| `--breakpoint-site-sm` | 32.5rem (520px) | Plan padding, two-column footer |
| `--breakpoint-site-nav` | **47.5rem (760px)**, proposed (today 901) | Phone header below this (tablet shows the links) |
| `--breakpoint-site-md` | 56.25rem (900px) | Single-column sections, scrubs off |
| `--breakpoint-site-wide` | 66.25rem (1060px) | Hero, machine and footer re-flow |

- In `site.css`, write queries as `@media (width < theme(--breakpoint-site-md))` after `@reference "../../styles/globals.css";`. [Hypothesis: confirm `@reference` resolves from a CSS file imported by a layout. It's the documented v4 pattern; if not, keep the literals and add a comment pointing at the token.]
- Tailwind's `md` (48rem), `lg` (64rem), `xl` (80rem) and `wide` (90rem) stay for app and inner-page utilities.

---

## 8. Motion

| Token | Value | Use |
|---|---|---|
| `--ease-site` | `cubic-bezier(.2, .7, .2, 1)` | Everything (repeated 5 times today) |
| `--motion-site-fast` | 150ms | Hover colour, press |
| `--motion-site` | 250ms | Buttons, toggles, chevrons |
| `--motion-site-slow` | 450ms | Scene items entering, mode swap |
| `--motion-site-entrance` | 1200ms (maximum) | One-shot hero sort |

Under `prefers-reduced-motion: reduce`, all durations become instant, as now. These replace 9 ad-hoc durations (.15–.7 s).

---

## 9. Interactive states

Colours are tokens from §1; ratios [Measured].

| Component | Rest | Hover | Active | Focus-visible | Disabled |
|---|---|---|---|---|---|
| Primary button (paper) | bg `--ink` #121317, fg #FFF (18.56) | bg `--iris-ink` #3A2FC2 (8.88) | `translateY(1px)` | 2px `--iris` outline, offset 3px (6.23 on paper) | bg `--ink-3` #5E616A, fg #FFF (6.19), `cursor: not-allowed`, no hover |
| Primary button (night) | bg #FFF, fg `--night` | bg `--iris-night` #A8A1FF (8.32 with night text) | same | 2px `--iris-night` (8.32 on night) | bg `--night-3`, fg `--night-ink-3` |
| Secondary button (paper) | transparent, fg ink, border `--line-control` #82848B (3.42) | border ink, bg ink at 5% | same | same ring | border `--rule`, fg `--ink-3` |
| Secondary button (night) | border `--night-line-control` #6A6C76 (3.63) | border night-ink, bg night-ink at 6% | same | `--iris-night` ring | border `--night-rule`, fg `--night-ink-3` |
| Ghost / nav link | fg `--ink-2` (8.22) | fg `--ink`, underline offset 4px | – | ring | fg `--ink-3` |
| Text link | fg `--iris` (6.23), underline offset 4px | fg `--iris-ink` | – | ring | – |
| Interactive card | sheet, `--rule` border | border `--line-control` | – | ring on the inner link | – |
| Input | border `--line-control` (3.74 on sheet), bg sheet | border `--ink-2` | – | 2px `--iris`, offset 1px | bg `--paper-2`, fg `--ink-3` |
| Switch segment | fg `--ink-3` | fg `--ink` | – | ring | pressed: bg `--ink`, fg #FFF (18.56) |
| Touch sizes | Buttons 48px (hero, menu), 44px (nav at ≤900); links ≥24px, 44px at ≤900 | | | | |

All transitions use `--motion-site` with `--ease-site`.

---

## 10. Paste-ready sketch

```css
/* styles/globals.css — inside @theme (values only) */
--color-ink-tertiary: #5E616A;
--color-line-control-site: #82848B;
--color-night-line-control: #6A6C76;
--color-ig-night: #E0559A;
--color-web-night: #2AA597;
--color-site-wait-mark: #B06A00;
--color-iris-mist: #8A82EB;

--type-display: clamp(2.75rem, 2.193rem + 2.286vw, 4.25rem);
--type-h1-page: clamp(2.25rem, 1.693rem + 2.286vw, 3.75rem);
--type-h2: clamp(2rem, 1.536rem + 1.905vw, 3.25rem);
--type-h2-sm: clamp(1.75rem, 1.471rem + 1.143vw, 2.5rem);
--type-h3: clamp(1.5rem, 1.314rem + .762vw, 2rem);
--type-stat: clamp(2.75rem, 2.286rem + 1.905vw, 4rem);
--type-stat-sm: clamp(1.5rem, 1.314rem + .762vw, 2rem);
--type-title: 1.25rem; --type-lede: clamp(1.0625rem, 1.016rem + .19vw, 1.1875rem);
--type-body: 1rem; --type-body-sm: .9375rem; --type-label: .875rem; --type-caption: .8125rem; --type-micro: .75rem;

--space-section: clamp(72px, 6vw + 40px, 128px);
--space-section-tight: clamp(48px, 4vw + 24px, 88px);
--space-head: clamp(32px, 2.5vw + 16px, 56px);
--space-band: clamp(56px, 48px + 1.5vw, 72px);
--gutter-site: clamp(16px, 3vw + 4px, 64px);
--container-site: 1240px;

--radius-site-xs: 6px; --radius-site-sm: 10px; --radius-site-md: 12px; --radius-site-lg: 18px; --radius-site-xl: 22px;

--breakpoint-site-sm: 32.5rem; --breakpoint-site-nav: 47.5rem; --breakpoint-site-md: 56.25rem; --breakpoint-site-wide: 66.25rem;

--ease-site: cubic-bezier(.2, .7, .2, 1);
--motion-site-fast: 150ms; --motion-site: 250ms; --motion-site-slow: 450ms;

/* styles/globals.css — .site block: semantic aliases, re-pointed on night */
.site {
  --s-bg: var(--paper); --s-surface: var(--sheet);
  --s-text: var(--ink); --s-text-2: var(--ink-2); --s-text-3: var(--ink-3);
  --s-line: var(--rule); --s-line-control: var(--color-line-control-site);
  --s-accent: var(--iris); --s-cta-bg: var(--ink); --s-cta-fg: var(--sheet); --s-cta-hover: var(--color-iris-ink);
  --s-ig: var(--ig); --s-web: var(--web);
}
.site .night {
  --s-bg: var(--night); --s-surface: var(--night-2);
  --s-text: var(--night-ink); --s-text-2: var(--night-ink-2); --s-text-3: var(--night-ink-3);
  --s-line: var(--night-rule); --s-line-control: var(--color-night-line-control);
  --s-accent: var(--iris-night); --s-cta-bg: var(--sheet); --s-cta-fg: var(--night); --s-cta-hover: var(--iris-night);
  --s-ig: var(--color-ig-night); --s-web: var(--color-web-night);
  --color-brand-strong: var(--color-iris-night);
}
.site { --gradient-brand: linear-gradient(var(--color-ink), var(--color-ink)); }
```

Check the exact `@theme` namespace names against Tailwind v4 before adding them (for example, `--radius-*` and `--breakpoint-*` generate utilities, and `--type-*` doesn't). Use the namespaced names only where a utility is wanted.
