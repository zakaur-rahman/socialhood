# Colour system audit: colours and surfaces

Scope: `apps/web/src` on `feature/ui-audit` (99f67be), brief sections 3, 4, 5, 10 and 11.
Read-only audit; no code was changed. Date: 2026-10-01.

**Stack.** Next.js 16.3.6, React 19.2.8, Tailwind CSS 4.3.3 configured in CSS only: there is no
`tailwind.config`; the tokens are in `@theme` in `src/styles/globals.css`. shadcn/ui v4 uses the
`radix-nova` style (`components.json`), with its semantic variables mapped onto our tokens in
`:root` and `@theme inline`. `src/styles/tokens.ts` mirrors the palette, `tokens.test.ts` checks
`globals.css` against that mirror, and the dev-only `/dev/tokens` page renders it.

**Prior decisions it was read against.** BUILD_SPEC §4.1–4.2 (UX-TOK-01, UX-TOK-02), UX-SH-01…04,
UX-INB-02…10, UX-SCR-*, UX-CMP-01, UX-A11Y-01…05 and D13 (dark only, "light mode is a token swap
later"). From CONFLICTS.md: C-002 (the `globals.css` additions; dark-only), C-018, C-048, C-063,
C-065 and C-066 (the redesigns: "layout from the mockups, colours from our tokens").

**How it was measured.** The scripts ran from a scratchpad and are not committed.
- Regex scans of every non-test `.ts`, `.tsx` and `.css` file (about 330 files) for hex, `rgb()`,
  `hsl()`, `oklch()` and `color-mix()` values, Tailwind palette utilities, arbitrary values, inline
  styles, token utilities, gradients, blur, shadows and state variants.
- The worktree's `globals.css` was compiled with the project's own Tailwind 4.3.3, against
  candidates from the Oxide scanner, to find colour classes that **generate no CSS**.
- The project's `cn` (shadcn's tailwind-merge replacement) was run on real class strings to see
  what survives merging.
- WCAG 2.x contrast was calculated with alpha compositing, so a translucent colour is measured
  on the surface it actually sits on.
- Colour distance is CIEDE2000 (ΔE00). Colour-vision deficiency was simulated with Viénot 1999
  (protanopia and deuteranopia).

---

## 1. Summary

The colour foundation is good, and most of it is used as intended:

- About **9 in 10 colour usages go through tokens**: roughly 2,600 token or alias utility uses,
  against 213 Tailwind palette utilities and about 30 hex literals.
- Every hex literal outside the token files mirrors a token, for consumers that can't read CSS
  variables (Clerk, `next/og`, the manifest).
- No colours leaked in from the owner's mockups.
- The danger trio (`danger`, `danger-fg`, `danger-fill`) and the brand's text-safe `brand-fg`
  are well designed. `danger-fg` is used correctly 121 times.

Where it falls short:

1. **States are where the system breaks.**
   - Primary gradient buttons (about 70) and ghost buttons (101) show **no visible hover**.
   - Shadcn's focus ring (`ring-ring/50`) is **2.1:1**. It is the only focus cue on 39 segmented
     controls and about 15 custom elements.
   - 13 form fields show focus only as a background change of 1.17:1.
   - Interactive edges (`border-line`/`border-input`, unchecked checkboxes) are **1.35:1**,
     against the spec's own 3:1 (UX-A11Y-01).
2. **The fix from UX-TOK-02 (white text on `#567FF8` is only 3.6:1) has come back on solid
   fills:**
   - the inbox platform switch,
   - Clerk's sign-in and sign-up buttons,
   - the skip link,
   - shadcn's `--primary`.
3. **Platform colours are used as text:** "Instagram" in the thread header is 2.73:1.
4. **Missing semantic layers lead to ad-hoc recipes:**
   - Soft status fills come in 2–4 opacities each, and the tone→class map is copied 4 times.
   - Hover is written 6 different ways.
   - Modal scrims are 10% or 60%.
   - About 200 `white`/`black` utilities would block D13's light-mode token swap.
5. **Surfaces don't separate:**
   - `field` and `panel` differ by 1.02:1.
   - Popovers and dialogs are the same colour as the cards under them.
   - Hover on a panel is numerically the same colour as `raised` (selected).

The proposal in §11 keeps every current value and name. It adds a small set of semantic tokens
(`on-brand`, `brand-strong`, `hover`, `pressed`, `scrim`, `overlay`, `line-control`, and three
`*-soft` tokens), remaps four shadcn aliases, and fixes the recipes in the primitives. That
removes most of the hardcoded colours without changing the look.

---

## 2. Current tokens

### 2.1 `@theme` colour tokens (`globals.css:13-48`)

Uses counts token utilities in any prefix or variant (`bg-`, `text-`, `border-`, `ring-`,
`from-`, `hover:` and so on) in non-test source, excluding `src/styles/`.

| Token | Value | Purpose (spec §4.2) | Uses | Files |
|---|---|---|---:|---:|
| `canvas` | `#000000` | App and thread background | 41 | 25 |
| `panel` | `#1F1F1F` | Sidebar, list pane, headers, composer bar, popovers | 176 | 102 |
| `field` | `#1D1D1D` | Inputs, incoming bubbles, segmented track | 96 | 59 |
| `raised` | `#2A2A2A` | Selected row, active segment, focused input, secondary button | 206 | 87 |
| `raised-hover` | `#333333` | Hover on raised surfaces | 6 | 4 |
| `line` | `rgb(255 255 255 / 0.10)` | Borders | 275 | 125 |
| `line-subtle` | `rgb(255 255 255 / 0.05)` | Faint borders | 49 | 36 |
| `line-strong` | `rgb(255 255 255 / 0.20)` | Emphasised borders | 18 | 17 |
| `fg` | `#FFFFFF` | Primary text | 133 | 72 |
| `fg-secondary` | `#9B9CA0` | Secondary and meta text, timestamps | 608 | 148 |
| `fg-disabled` | `#71717A` | Disabled controls and placeholders only | 8 | 7 |
| `brand` | `#567FF8` | Fills, borders, dots, focus ring | 59 | 40 |
| `brand-deep` | `#20338A` | Gradient start | 3 | 3 |
| `brand-fg` | `#9DB5FF` | Brand text and icons on dark | 151 | 92 |
| `brand-soft` | `rgb(86 127 248 / 0.15)` | Soft brand fills | 59 | 46 |
| `brand-line` | `rgb(86 127 248 / 0.35)` | Brand borders | 28 | 25 |
| `shell-1` | `#3352CC` | Logo tile and Upgrade (gradient stop) | 1 | 1 |
| `shell-2` | `#1C2D70` | Logo tile and Upgrade (gradient stop) | 1 | 1 |
| `success` | `#22C55E` | Success | 57 | 30 |
| `warning` | `#FB923C` | Warning | 85 | 40 |
| `danger` | `#EF4444` | Danger icons and borders | 63 | 39 |
| `danger-fg` | `#FCA5A5` | Danger text on dark | 121 | 61 |
| `danger-fill` | `#C53030` | Failed bubble and destructive button fill | 28 | 15 |
| `instagram` | `#BE185D` | Platform | 9 | 8 |
| `whatsapp` | `#16A34A` | Platform | 9 | 8 |
| `facebook` | `#2563EB` | Platform (marketing "later" tile, one avatar stop) | 2 | 2 |
| `linkedin` | `#1E40AF` | Platform (only an avatar gradient stop) | 1 | 1 |

`shell-1` and `shell-2` are used mostly through `bg-shell-gradient` (8 uses). `brand-deep` is
mostly used through the gradients.

### 2.2 shadcn aliases (`globals.css:99-121`)

| Alias | Maps to | Uses | Generates CSS? |
|---|---|---:|---|
| `--background` / `--foreground` | canvas / fg | 6 / 19 | yes |
| `--card` / `--card-foreground` | panel / fg | 0 / 0 | card yes; **card-foreground no** |
| `--popover` / `--popover-foreground` | panel / fg | 9 / 7 | popover yes; **popover-foreground no** |
| `--primary` / `--primary-foreground` | brand / **literal `#FFFFFF`** | 13 / 5 | yes |
| `--secondary` / `--secondary-foreground` | raised / fg | 4 / 3 | secondary yes; **secondary-foreground no** |
| `--muted` / `--muted-foreground` | field / fg-secondary | 14 / 15 | yes |
| `--accent` / `--accent-foreground` | raised / fg | 6 / 12 | accent yes; **accent-foreground no** |
| `--destructive` | danger | 44 | yes |
| `--border` / `--input` / `--ring` | line / line / brand | 5 / 16 / 35 | yes |

`@theme inline` (`globals.css:113-121`) leaves out the four `*-foreground` aliases marked "no".
Compiling the worktree with Tailwind 4.3.3 produced no CSS for `text-popover-foreground`,
`text-secondary-foreground`, `text-accent-foreground` or their variants (`focus:`, `data-open:`,
`aria-expanded:`, `group-focus/…:`). See COL-009.

### 2.3 Custom colour utilities (`globals.css:51-97`)

| Utility | Definition | Uses / files |
|---|---|---:|
| `bg-brand-gradient` | `135deg, #20338A → #4467E6` | 71 / 52 |
| `bg-brand-gradient-decor` | `135deg, #20338A → #567FF8` | 9 / 9 |
| `bg-shell-gradient` | `135deg, #3352CC → #1C2D70` | 8 / 8 |
| `automation-line-active` | dashed `canvas` over `brand → brand-deep`, animated; static under reduced motion | 1 |
| `text-shimmer` | `fg-secondary`/`fg` sweep clipped to text; plain under reduced motion | 1 |

Base layer (`globals.css:123-129`): every border defaults to `line`; `body` is canvas on fg;
`:focus-visible` is a 2 px `brand` outline offset by 2 px; `::placeholder` uses `fg-disabled`.

---

## 3. Primary and semantic colours

### 3.1 Brand (primary)

- **What the brand is.** `brand #567FF8` is the brand colour. Primary actions use
  `bg-brand-gradient` (`#20338A → #4467E6`), which UX-TOK-02 chose so white text reaches
  4.85:1 at its light end.
- **Where it's used.** About 380 brand-family uses:
  - `brand` 59
  - `brand-fg` 151: roughly 41 links, 39 `brand-soft` chips, 22 icons, and the rest active
    states and AI labels
  - `brand-soft` 59
  - `brand-line` 28
  - `bg-brand-gradient` 71
  - `bg-brand-gradient-decor` 9
- **Overuse: no.** The "one accent" rule (§4.1) holds. Customer content stays neutral, and
  brand marks outgoing bubbles, primary actions, selection and AI. The weakest spot is
  decorative brand-tinted icon tiles (every `SettingsCard` icon, and the billing meter icons).
  They are tolerable, but they dilute the accent.

**How primary actions are built.** There is no primary Button variant.

- 54 `<Button>`s use the default variant and add `className="bg-brand-gradient text-white"`.
  About 12 more hand-rolled buttons and links do the same, for example the composer Send button
  (`Composer.tsx:414`).
- No `<Button>` relies on the plain default (`bg-primary`). Every default-variant Button is
  overridden.

**States of the primary action:**

| State | What happens | Verdict |
|---|---|---|
| Hover | `cn` treats `bg-brand-gradient` as a background colour, so it drops `bg-primary` but keeps `hover:bg-primary/80`. That rule paints `background-color` underneath the gradient image, so nothing visibly changes. Checked against `cn`'s output and the compiled CSS (`.hover\:bg-primary\/80:hover { background-color: … }`). Only 3 of about 70 gradient controls have a hover (`hover:brightness-110`: `data-deletion/page.tsx:110`, `marketing/primitives.tsx:36`, `UsageCard.tsx:106`). | **Missing** (COL-005) |
| Active | `active:translate-y-px` only, with no colour change. | Minimal |
| Focus | `focus-visible:border-ring ring-3 ring-ring/50`: a 1 px solid brand border (4.54:1 on panel) plus a 3 px ring at 2.10:1. | Passes only through the 1 px border (COL-003) |
| Disabled | `disabled:opacity-50` on the gradient. Send buttons use `bg-raised text-fg-disabled` instead. | Inconsistent (COL-020) |
| Contrast | White on `#20338A` is 11.04:1; white on `#4467E6` is 4.85:1. | Pass |

**Solid brand behind white text fails AA at 3.63:1:**
- `PlatformStrip.tsx:54`, the active segment
- `(marketing)/layout.tsx:25`, the skip link
- `clerk-appearance.ts:10-11`, the Clerk primary button
- shadcn's `--primary` (Button default, Badge default, AvatarBadge)

See COL-001.

### 3.2 The rest of the semantic set

| Role | Token(s) | What exists | Coherent? |
|---|---|---|---|
| Secondary | `raised` (`--secondary`) | 56 `variant="secondary"` buttons. Hover is a `color-mix` 5% toward white (`button.tsx:15`), the only arbitrary colour in the primitives. | OK; the hover step is weak (about 1.1:1) |
| Accent | `raised` (`--accent`) | Menu and select highlight (`focus:bg-accent`) | Same value as secondary and selected |
| Muted | `field` (`--muted`) | Ghost hover, skeleton, avatar fallback, dialog footer | The muted surface is darker than panel, so it vanishes on panel (COL-005, COL-020) |
| Destructive | `danger` (`--destructive`) | shadcn variants use `text-destructive`, the icon colour, as text (COL-008). Our own destructive buttons use `bg-danger-fill text-white hover:bg-danger-fill/90` (12 call sites). | Two systems |
| Success | `success` | Text 28, fills `/15` 13, `/10` 3, borders `/40` 2, `/30` 1 | No soft or line token |
| Warning | `warning` | Text 41, fills `/15` 20, `/10` 4, borders `/40` 4, `/30` 1 | No soft or line token; the spec even names `bg-warn-soft` (UX-SCR-03), which doesn't exist |
| Danger | `danger`, `danger-fg`, `danger-fill` | Text in `danger-fg` (121) and icons in `danger` (7). Soft fills are `/15` 12, `/10` 8, plus the shadcn `destructive/10, /20, /30`. | The best-structured role, but soft fills drift |
| Info | — | No token. `brand-soft` and `brand-fg` act as info ("Scheduled", Lead, AI). | Acceptable; make it an explicit alias |

**Verdict.** The system is semantic for brand and danger, half-semantic for success and
warning, and missing a layer for states (hover, pressed, scrim) and for soft status fills.

---

## 4. Hardcoded colours

### 4.1 Totals

| Kind | Count | Where |
|---|---:|---|
| Hex literals outside `globals.css` and `tokens.ts` | 30 (+1 false positive, `rules.ts:35` "abc#def") | `clerk-appearance.ts` 13, `marketing/og.tsx` 10, `marketing/primitives.tsx` 4 (`#fff` and `#20338A` ×3, SVG logo fills), `manifest.ts` 2, `app/layout.tsx` 1 |
| `rgb()` / `rgba()` | 4 | `clerk-appearance.ts:19, 24` (border, modal backdrop); `og.tsx:32` (radial glow) |
| `hsl()` / `oklch()` | 0 (one `color-mix(in_oklch…)`) | `ui/button.tsx:15` |
| Tailwind palette utilities | **213**: `white` 198, `black` 15 | 100 files |
| Arbitrary colour values | 7, all built on tokens | `button.tsx:15` color-mix; `BillingPage.tsx:270`, `Hero.tsx:15`, `FinalCta.tsx:15` radial gradients; `Threads.tsx:183`, `CropDialog.tsx:150` shadows; `AppSidebar.tsx:113` mask |
| Inline style colours | 6 | all in `og.tsx` (Satori can't read CSS variables); `AppSidebar.tsx:102` grain image |

No mockup colour leaked into code. The only hex values are mirrors of tokens.

### 4.2 Palette utilities by class

| Class | Uses | Typical use | Same value as |
|---|---:|---|---|
| `text-white` | 108 | 66 on `bg-brand-gradient`, 15 on `bg-danger-fill`, 5 on `bg-brand`, 3 on platform fills, 2 on shell gradient, 1 on avatars | `fg` (but semantically "on brand") |
| `bg-white/5` (incl. `hover:`, `data-[state=open]:`) | 43 | Hover on rows and menus, neutral chips, kbd | `line-subtle`; on panel it composites to `#2A2A2A` = `raised` |
| `bg-white/10` | 25 | Stronger hover, chip on tint, meter track | `line`; on panel `#353535` ≈ `raised-hover` |
| `bg-white/15` | 6 | Hover on tinted banners, progress | — |
| `bg-white/20` | 3 | Hover on media overlays | `line-strong` |
| `bg-white/[0.03]` | 2 | `UsageCard.tsx:80`, `WeekView.tsx:205` | Input `dark:bg-input/30` (`#262626` on panel) |
| `text-white/75`, `/80`, `/90` ×2 | 4 | Bubble meta and labels, marketing CTA | — |
| `border-white/30`, `/60`; `ring-white/40`; `stroke-white/10`, `/20` | 5 | Bubble cards, quick replies, platform dot ring, progress rings | — |
| `bg-white`, `hover:bg-white/90` | 2 | Marketing "Start free" button | — |
| `bg-black/10` | 3 | shadcn Dialog, AlertDialog and Sheet scrims | — |
| `bg-black/60` | 3 | AskPanel, AgentSettings overlay, AttachmentTray failure | Clerk `colorModalBackdrop` 0.6 |
| `bg-black/20`, `/50`, `/70`, `bg-black` | 7 | Media overlays (AttachmentView, AttachmentTray) | — |
| `shadow-black/40`, `/60` | 2 | SaveBar, marketing MobileMenu | — |

### 4.3 Top offenders (palette utilities per file)

| File | Uses |
|---|---:|
| `components/composer/MediaTray.tsx` | 10 |
| `components/inbox/AttachmentTray.tsx` | 8 |
| `components/inbox/MessageBubble.tsx` | 8 |
| `components/billing/BillingPage.tsx` | 7 |
| `components/inbox/AttachmentView.tsx` | 6 |
| `components/agent/RunView.tsx`, `automations/TemplateGallery.tsx`, `marketing/FinalCta.tsx` | 5 each |
| `ai/SuggestionCard.tsx`, `automations/PreviewPane.tsx`, `inbox/Composer.tsx`, `push/InstallPrompt.tsx`, `shell/UsageCard.tsx` | 4 each |

The rest are spread across 87 files, with 1–3 uses each.

**Media overlays are legitimately hardcoded:** `bg-black/N` over photos and video in
AttachmentTray and AttachmentView. Scrims over user media must stay dark in any theme, so they
should stay literal or use a `media-scrim` alias. They are not token debt.

### 4.4 Hex mirrors

- `clerk-appearance.ts` mirrors 10 tokens; Clerk computes shades and can't read variables.
- `og.tsx` mirrors 10 tokens; Satori can't read variables.
- The manifest and viewport `#000000` (×3) must be literal.
- The Logo SVG fills (`primitives.tsx:12-15`) could use `fill="currentColor"` and classes.

None of these are covered by `tokens.test.ts`, which checks only `globals.css`. See COL-019.

---

## 5. Near-duplicates

ΔE00 is computed after alpha compositing on the surface the colour actually sits on. Below 1 is
indistinguishable; 1–3 is barely visible side by side; below 5 is a near-duplicate.

| Group | Members (value → ΔE00) | Verdict |
|---|---|---|
| **N1** Hover equals selected | `raised #2A2A2A` ↔ `bg-white/5` on panel `#2A2A2A` → **0.06** | The same colour. Row hover (`ConversationRow.tsx:63`, `sidebar-styles.ts:11`) equals the selected fill (`:65`, `:13`). Only the brand bar tells them apart. |
| **N2** Field ≈ panel | `field #1D1D1D` ↔ `panel #1F1F1F` → **0.63** (1.02:1) | Inputs on cards and the skeleton default are invisible against the card. `field` only reads on `canvas` (1.25:1). |
| **N3** Strong hover ≈ raised-hover | `bg-white/10` on panel `#353535` ↔ `raised-hover #333333` → 0.77 | Two names for one step |
| **N4** Input backgrounds | shadcn Input `dark:bg-input/30` on panel `#262626` ↔ `raised` 1.35 ↔ `field` 2.74 | Two input looks (COL-011) |
| **N5** Dark blues | `brand-deep #20338A` ↔ `shell-2 #1C2D70` → **4.26**; ↔ `linkedin #1E40AF` 6.12 | Two gradients with almost the same dark stop, in opposite directions (COL-013) |
| **N6** Mid blues | gradient end `#4467E6` (not a token) ↔ `facebook #2563EB` → **2.49**; `shell-1 #3352CC` ↔ `linkedin` 6.67 ↔ `facebook` 6.78 | `facebook` and `linkedin` duplicate the brand ramp; `linkedin` exists only as an avatar stop |
| **N7** Soft fills | `brand-soft` ↔ `bg-brand/20` 2.90; `danger/15` ↔ `danger/10` 3.90 ↔ `destructive/20` 3.34; `warning/15` ↔ `warning/10` 3.69 | Opacity drift of one role (COL-007) |
| **N8** Greens | `success #22C55E` ↔ `whatsapp #16A34A` → 9.64 | Distinct enough. They shouldn't be paired in one gradient, though (avatar pair 3). |
| **N9** Reds | `danger #EF4444` ↔ `danger-fill #C53030` → 10.6 | Intentional: the text-safe fill. Keep. |

**Consolidation, without adding colours:**
- N1 and N3: name the overlays (`hover` = white/5, `pressed` = white/10). That replaces 68
  white-alpha utilities and gives `--accent` a meaning.
- N2: keep `field` (it carries the incoming bubbles on canvas). Make inputs identifiable by
  their edge (`line-control`) rather than their fill.
- N4: put all inputs on `field`.
- N5 and N6: promote `#4467E6` to `brand-strong`. Scope `shell-*` to the logo and Upgrade.
  Retire `linkedin`, or move it into an avatar palette.
- N7: one `*-soft` token per status at 15%, the majority value already.

---

## 6. Backgrounds and layering

| Layer | Token today | Value | Where |
|---|---|---|---|
| App | `canvas` | `#000000` | `body`, thread area, page background, marketing |
| Page | `canvas` | `#000000` | Non-inbox pages sit on canvas, with content in panels |
| Sidebar | `panel` | `#1F1F1F` | Floating card (`AppSidebar.tsx:94`) with grain at 5% (`:101`) |
| Mobile drawer | **`canvas`** | `#000000` | `MobileNav.tsx:39`; the desktop sidebar is panel, so they differ |
| Header | `panel` | `#1F1F1F` | List header, thread header, mobile top bar |
| Card | `panel` | `#1F1F1F` | 160 `bg-panel` uses; `--card` is unused |
| Modal / sheet | `--popover` = panel (54 overlay call sites set `bg-panel`, 57 `border-line`, 21 `shadow-xl`) | `#1F1F1F` | Same colour as the cards beneath |
| Popover / menu | panel | `#1F1F1F` | Same colour as the cards beneath |
| Tooltip | `bg-foreground` | **`#FFFFFF`** | The only light surface in the app (`tooltip.tsx:44`); black text, 21:1 |
| Toast | sonner `theme="dark"` | **`#000`**, border `hsl(0 0% 20%)` | Not on tokens (COL-018) |
| Input | `field` or `#262626` | `#1D1D1D` / `#262626` | Two looks (COL-011) |
| Hover | `bg-white/5`, `hover:bg-raised`, `dark:hover:bg-muted/50`, `bg-white/10`, `bg-white/[0.03]`, `color-mix` | 6 recipes | COL-005 |
| Selected | `raised` + brand bar | `#2A2A2A` | Bar is 3 px in rows (`ConversationRow.tsx:68`), 2 px in the sidebar (`sidebar-styles.ts:13`), 2 px inset shadow in Threads (`Threads.tsx:183`) |
| Disabled | `opacity-50` (17), `opacity-60` (4), `bg-raised text-fg-disabled` (send buttons) | — | COL-020 |
| Scrim | `bg-black/10` + blur (shadcn), `bg-black/60` (custom, Clerk) | — | COL-010 |

Contrast between layers (non-text, so this is about legibility rather than an AA target):

| Pair | Ratio |
|---|---:|
| panel vs canvas | 1.27:1 |
| field vs canvas | 1.25:1 |
| raised vs panel | 1.15:1 |
| raised-hover vs raised | 1.14:1 |
| **field vs panel** | **1.02:1** |
| **hover (white/5 on panel) vs raised** | **1.00:1** |
| **popover (panel) vs card (panel)** | **1.00:1** |
| **`bg-black/10` scrim over canvas vs canvas** | **1.00:1** (over panel 1.04:1) |
| `bg-black/60` scrim over panel vs panel | 1.18:1 |

**Elevation in dark mode.** The ladder is canvas → panel → raised, with raised doubling as
hover and selected. It reads for in-page structure: cards on the page, a selected row inside a
card. It doesn't read for **overlays**. Popovers, menus, dialogs and sheets use the same `panel`
as the cards they open over, with a 10% hairline. `shadow-xl` is black and so invisible on
near-black. The shadcn scrim is 10% black, which does nothing on a black page. Dark interfaces
normally signal elevation by getting lighter, and here nothing does.

**Pure black and white.**
- Pure black: the canvas (`#000`, intentional: v1's look and kind to OLED screens) and one
  `hover:bg-black` (`AttachmentTray.tsx:95`).
- Pure white: text `fg` (21:1 on canvas), the tooltip surface, the marketing "Start free" button
  (`FinalCta.tsx:28`), and the Ask "Stop" button `bg-fg` (`AskComposer.tsx:110`).
- Body text mostly sits on `panel` (16.5:1), so halation from white on black is limited to page
  titles and thread dates.
- No action recommended: it is the owner's chosen look.

---

## 7. Contrast

Text needs 4.5:1. Non-text (icons, control edges, focus indicators, chart marks) needs 3:1 (WCAG
1.4.11, and UX-A11Y-01). Translucent colours are composited on the stated surface.

### 7.1 Text on surfaces

| Text | canvas | panel | field | raised | raised-hover | hover (white/5 on panel) |
|---|---:|---:|---:|---:|---:|---:|
| `fg` `#FFF` | 21.00 | 16.48 | 16.86 | 14.35 | 12.63 | 14.31 |
| `fg-secondary` `#9B9CA0` | 7.66 | 6.01 | 6.15 | 5.23 | 4.61 | 5.22 |
| `fg-disabled` `#71717A` (placeholders) | **4.35 ✗** | **3.41 ✗** | **3.49 ✗** | **2.97 ✗** | **2.61 ✗** | **2.96 ✗** |
| `brand-fg` `#9DB5FF` | 10.49 | 8.23 | 8.42 | 7.17 | 6.31 | 7.15 |

### 7.2 Key pairs

| Pair | Ratio | AA | Where |
|---|---:|:---:|---|
| White on `bg-brand-gradient` start `#20338A` | 11.04 | ✓ | Primary buttons, bubbles |
| White on `bg-brand-gradient` end `#4467E6` | 4.85 | ✓ | Same |
| **White on `brand #567FF8` (solid)** | **3.63** | **✗** | `PlatformStrip.tsx:54` (text-xs), skip link, Clerk primary button, shadcn `--primary` |
| White on `bg-brand-gradient-decor` end `#567FF8` | 3.63 | icon ✓ / text ✗ | Only behind an icon (`TemplateGallery.tsx:199`), so it passes as non-text |
| `white/75` on gradient end (bubble template label) | 3.46 | ✗ (worst case) | `MessageBubble.tsx:103`; the label sits top-left, near `#20338A` (6.92), so the real risk is low |
| `white/90` on gradient end | 4.26 | ✗ (worst case) | `MessageBubble.tsx:165` |
| White on `shell-1` / `shell-2` | 6.52 / 12.66 | ✓ | Logo, Upgrade |
| White on `danger-fill` | 5.47 | ✓ | Failed bubble, destructive buttons |
| White on `danger-fill/90` (hover) | 6.20 | ✓ | |
| `danger-fg` on panel / on `danger/15` / on `danger/10` | 8.68 / 7.42 / 7.87 | ✓ | |
| **`danger #EF4444` as text on panel** | **4.38** | **✗** | `DropdownMenuItem variant="destructive"` (`post-parts.tsx:227`) |
| **`danger` text on `destructive/20` over panel** | **3.51** | **✗** | `AlertDialogAction variant="destructive"` "Cancel plan" (`BillingPage.tsx:315`); menu item when highlighted |
| `warning` on panel / on `warning/15` | 7.28 / 5.56 | ✓ | |
| `success` on panel / on `success/15` | 7.23 / 5.57 | ✓ | |
| `brand-fg` on `brand-soft` (panel) | 6.80 | ✓ | Chips, AI pill |
| `fg-secondary` on `brand-soft` (panel) | 4.97 | ✓ | |
| **`fg-secondary` on `bg-white/10` (panel)** | **4.45** | **✗** (marginal) | Billing neutral badge (`BillingPage.tsx:64`); the other tone maps use `/5` (5.22) |
| **`fg-secondary/70` on panel** | **3.66** | **✗** | Sidebar group labels "ENGAGE" and "GROW", 11 px (`AppSidebar.tsx:257`) |
| **`instagram #BE185D` as text on panel** | **2.73** | **✗** | Thread header "Instagram" (`ThreadHeader.tsx:26, 100`) |
| `whatsapp` as text on panel | 5.00 | ✓ | Same header |
| `brand` as text on panel / on raised | 4.54 / **3.96 ✗** | ✓ / ✗ | Button `link` variant (2 uses), `text-brand` |
| White on `instagram` / `whatsapp` | 6.04 / **3.30** | ✓ / icon only | Platform badges carry glyphs only (3:1 needed), so they pass |
| White on `facebook` / `linkedin` | 5.17 / 8.72 | ✓ | |
| Black on white tooltip | 21.00 | ✓ | |
| White in sending bubble (`brand/60`, 80% opacity) | 6.45 | ✓ | |
| `danger-fg` on `bg-black/60` over a white photo | 3.03 | ✗ (worst case) | `AttachmentTray.tsx:78` |
| **Avatar initial: white on `instagram → warning`** | mid **3.84**, end **2.26** | **✗** | `lib/inbox/format.ts:187`; initial is 16–18 px semibold, so 4.5:1 applies |
| **Avatar: `whatsapp → success`** | mid **2.73**, end **2.28** | **✗** | `format.ts:188` |
| **Avatar: `danger-fill → warning`** | mid **3.54**, end **2.26** | **✗** | `format.ts:190` |
| Avatar: `brand-deep → brand` | mid 6.20, end 3.63 | ✓ / ✗ at the light corner | `format.ts:186` |
| Avatar: `shell-1 → shell-2`; `linkedin → facebook` | ≥ 5.17 | ✓ | |

### 7.3 Non-text (3:1)

| Pair | Ratio | Pass | Where |
|---|---:|:---:|---|
| Global focus outline `brand` on canvas / panel / raised | 5.79 / 4.54 / 3.96 | ✓ | `globals.css:127` (links and plain buttons) |
| **shadcn focus ring `ring-ring/50` on panel / canvas** | **2.10 / 2.12** | **✗** | Sole cue on Tabs (8), ToggleGroup (31 items) and about 15 custom elements (COL-003) |
| **`focus:bg-raised` as the only focus cue (field → raised)** | **1.17** | **✗** | 13 fields in 10 files (COL-003) |
| **Composer focus: border white/10 → white/20** | **1.42** | **✗** | `Composer.tsx:292` |
| **`border-line` / `border-input` control edge vs panel** | **1.35** | **✗** | Inputs, Select, unchecked Checkbox (COL-004) |
| `border-line-strong` vs panel | 1.91 | ✗ | |
| `border-brand-line` vs panel | 1.65 | ✗ | Decorative borders only; fine |
| Switch on (`bg-primary`) vs panel | 4.54 | ✓ | |
| Switch off track vs panel | 1.27 | (✓) | The white thumb (16:1) carries the state |
| Unread dot `brand` on panel / on selected raised | 4.54 / 3.96 | ✓ | |
| **Meter fill start `#20338A` vs `raised` track** | **1.30** | ✗ | Decor-gradient meters; the value is also in text, so supplementary |
| Meter track `raised` vs panel | 1.15 | ✗ | Supplementary |
| Chart series vs panel: success / danger / neutral / warning / brand | 7.23 / 4.38 / 6.01 / 7.28 / 4.54 | ✓ | |
| **Account ring `instagram` vs panel** | **2.73** | **✗** | Schedule account filter (`lib/schedule/format.ts:92`) |
| Account rings `brand` vs `brand-fg` (adjacent in one palette) | 1.81, same hue | — | COL-015 |
| `fg-disabled` draft card bar vs panel | 3.41 | ✓ | |

---

## 8. Blur and glass

| Where | What | Intent | Cost and verdict |
|---|---|---|---|
| `ui/dialog.tsx:42`, `ui/alert-dialog.tsx:39`, `ui/sheet.tsx:40` | `bg-black/10 supports-backdrop-filter:backdrop-blur-xs` (4 px) over the whole viewport | shadcn default, never reconsidered | The 10% scrim is invisible on black; the blur does the separating. Full-viewport blur during open and close animations is the costliest effect in the app on low-end phones. Replace with a 60% scrim and drop the blur (COL-010, COL-017). |
| `settings/SaveBar.tsx:70` | `bg-panel/95 backdrop-blur shadow-2xl` on a sticky bar | Glassy save bar | At 95% opacity the blur is invisible but still adds a compositing layer that re-blurs on every scroll frame. Use opaque `bg-panel` (COL-017). |
| `marketing/SiteHeader.tsx:13` | `bg-canvas/85 backdrop-blur supports-[backdrop-filter]:bg-canvas/70` | Classic sticky marketing header | Intentional, with a fallback. Keep. |

Other translucent surfaces:
- **Marketing glass panels:** `bg-panel/40` to `/70` (×7). Fine on marketing pages.
- **Settings "inner panels":** `bg-field/60` (×10, AI, Agent, Billing, Connections, Details).
  At 60% over panel this is `#1E1E1E`, indistinguishable from panel (ΔE00 < 1). The inner
  panels are visible only through their border.
- **Media chips:** `bg-canvas/70`–`/85` (×13) on photos. Correct.

Nothing is "too much" glass. The cost is concentrated in the shadcn overlays.

---

## 9. Gradients

| Gradient | Purpose | Uses |
|---|---|---|
| `bg-brand-gradient` | Primary buttons (about 66), outgoing bubbles, count badges (sidebar, Scheduled), Ask tile, marketing step numbers, **8 px notification dots** (`NotificationsButton.tsx:39, 122`) | 71 |
| `bg-brand-gradient-decor` | Meters and progress: UsageMeter, Billing, lead score, intents, analysed share, upload and source progress; 2 decorative tiles | 9 |
| `bg-shell-gradient` | Logo tile (auth, MobileNav, WorkspaceMenu, marketing), Upgrade; **also** the plan hero icon (`BillingPage.tsx:274`), the preview "me" avatar (`PreviewPane.tsx:77`) and the marketing CTA panel | 8 |
| Avatar gradients (`bg-linear-135` + 6 `from-`/`to-` pairs) | Contact initials (`lib/inbox/format.ts:185-192`, `ContactAvatar.tsx:40`) | 6 pairs |
| `automation-line-active` | Editor gutter while active | 1 |
| `text-shimmer` | Ask step label | 1 |
| Arbitrary radial glows | Plan hero (`BillingPage.tsx:270`, brand-soft), Hero (`Hero.tsx:15`, brand-soft), FinalCta (`FinalCta.tsx:15`, line-strong), OG image | 4 |
| `[mask-image:linear-gradient]` | Sidebar scroll fade (`AppSidebar.tsx:113`) | 1 |
| `bg-linear-to-t from-canvas/90` | Reel preview caption scrim (`PostPreview.tsx:275`) | 1 |

**Consistency problems.**

1. **Two blue gradients that run in opposite directions.** Brand goes dark to light
   (`#20338A → #4467E6`). Shell goes light to dark (`#3352CC → #1C2D70`). Their dark stops are
   ΔE00 4.3 apart. Choosing between them is arbitrary outside the spec's two shell uses.
2. **The same meaning drawn three ways:**
   - **Unread:** a solid `bg-brand` dot in the conversation row (`ConversationRow.tsx:98`, as
     the spec says), but a gradient dot in notifications.
   - **Usage meters:** a decor gradient on a `raised` track (Billing, UsageMeter), solid
     `bg-brand` on `bg-white/10` (sidebar `UsageCard.tsx:11, 93`, the same AI-credits number),
     and solid `bg-brand` on `bg-field` (`ScheduleRail.tsx:117`).
3. **Avatar gradients use semantic and platform colours as identity**: warning, success,
   danger-fill. Three of the six pairs fail contrast for the initial (COL-014).
4. **Stops are hex literals inside `@utility`**, so they can't follow a theme swap.
   `tokens.test.ts` pins the literal string.

**Readability.** Text on `bg-brand-gradient` passes, at 4.85:1 or better everywhere.
`text-shimmer` falls back to plain `fg-secondary` under reduced motion. The radial glows sit
behind text at 15% brand and don't affect contrast.

**Recommended controlled gradient system** (four gradients, each with one job; stops are
variables):

| Name | Stops | Allowed on | Text on it |
|---|---|---|---|
| `gradient-brand` (today's `bg-brand-gradient`) | `var(--color-brand-deep)` → `var(--color-brand-strong)` | Primary actions, outgoing bubbles, count badges | `on-brand`, ≥ 4.85:1 |
| `gradient-brand-decor` | `brand-deep` → `brand` | Meters, progress, decorative tiles. Never under text. | Icons only |
| `gradient-shell` | `shell-1` → `shell-2` | Logo tile and Upgrade only (UX-SH-01) | `on-brand` |
| `glow-brand` (one radial utility) | `brand-soft` → transparent | Hero, plan hero. At most one per view. | Any |

Rules that go with them:
- Dots, bars and other marks under 12 px are solid (`brand`, not a gradient).
- All meters use `gradient-brand-decor` on a `raised` track, turning `warning` at 80% and
  `danger` at 100%.
- The avatar palette is separate (§11).

---

## 10. Charts and data colours

| Chart | Colours | Accessible? |
|---|---|---|
| Automation daily runs (`StatsPane.tsx:122-185`) | Runs `brand`, failures `danger` stacked with a 2 px gap; legend; `sr-only` table | ✓ Good pattern: colour plus legend plus table. Both series reach 3:1 or more on panel. |
| 7-day trend line (`TrendLine.tsx:29`) | `text-brand` stroke, 2 px | ✓ `aria-hidden`, and the count is in text |
| Sentiment bar (`SentimentBar.tsx:4-8`, `SentimentCard.tsx:7-11`) | `success` / `fg-secondary` / `danger`, 1 px gaps, `raised` track; spam `warning` in the legend | Mostly ✓. Every series reaches 4.38:1 or more on panel. Under deuteranopia, success vs danger drops from ΔE76 127 to 13.6, but the neutral grey usually separates them and the legend gives the numbers, so colour isn't the only cue. |
| Top intents (`TopIntentsCard.tsx:38`) | `gradient-brand-decor` bars on `raised` | ✓ Counts are in text |
| Usage and lead meters | Decor gradient → `warning` → `danger`; three recipes (§9) | The fill start is 1.30:1 against the track, but the value is in text |
| Schedule account colours (`lib/schedule/format.ts:92-93`) | `brand`, `instagram`, `warning`, `whatsapp`, `brand-fg`, `fg-secondary` | ✗ An orange ring reads as a warning. `brand` and `brand-fg` are one hue (1.81:1). The `instagram` ring is 2.73:1 against panel. Under protanopia, `whatsapp` vs `warning` drops to ΔE76 9.2. |
| Post status (`lib/schedule/format.ts:28-35`) | Left border `brand`, `success`, `danger` or `fg-disabled`, plus a labelled chip | ✓ The label carries the meaning |

There is no chart palette. Data colours reuse status tokens, which is right for status charts
(runs and failures, sentiment). Categorical uses (accounts, avatars) improvise from status and
platform tokens instead. The proposal adds aliases only, with no new hues, plus a separate
identity palette.

---

## 11. Proposed semantic colour tokens

Principles:
- Keep every current value and name (the spec, `tokens.ts` and tests stay valid).
- Add tokens only where a role exists today but is hand-written.
- Express states as overlays, so they work on any surface and survive D13's light-mode swap.

### 11.1 Surfaces and states

| Token | Value | Status | Replaces today |
|---|---|---|---|
| `canvas` | `#000000` | keep | — |
| `panel` | `#1F1F1F` | keep (`--card` → panel) | — |
| `overlay` | `#262626` | **new name** (the value already exists: shadcn Input's white/3 on panel) | Popovers, menus, dialogs, sheets, toasts. `--popover` → overlay; the 54 `bg-panel` overrides on overlay content go. |
| `field` | `#1D1D1D` | keep | All inputs (Input, SelectTrigger, Textarea, raw), incoming bubbles, segmented tracks. Input and Select drop `bg-transparent dark:bg-input/30`. |
| `raised` | `#2A2A2A` | keep | Selected, active segment, secondary button, skeleton, meter track |
| `raised-hover` | `#333333` | keep | Hover on raised |
| `hover` | `rgb(255 255 255 / 0.05)` | **new** (today's `bg-white/5` value, so the look doesn't change) | 43 `bg-white/5`, ghost `dark:hover:bg-muted/50`, outline `dark:hover:bg-input/50`, `hover:bg-raised` on rows. `--accent` → hover. |
| `pressed` | `rgb(255 255 255 / 0.10)` | **new** (today's `bg-white/10`) | 25 `bg-white/10`, `/15`, `data-[state=open]` |
| `scrim` | `rgb(0 0 0 / 0.60)` | **new** (spec UX-SH-02's `bg-black/60`, Clerk's 0.6, AskPanel) | shadcn `bg-black/10 + blur` (×3), `bg-black/60` (×3) |
| `media-scrim` | alias of `black` | optional | Overlays on photos and video, which stay dark in any theme |

### 11.2 Lines and focus

| Token | Value | Status | Use |
|---|---|---|---|
| `line`, `line-subtle`, `line-strong` | unchanged | keep | Dividers, card edges |
| `line-control` | `#6B6B6B` (3.09:1 on panel, 3.16:1 on field, 3.94:1 on canvas) | **new** | Checkbox and radio edges (required). Input, Select and Textarea edges if the owner accepts the change (COL-004). |
| `ring` (`--ring`) | `brand` | keep | One recipe: `outline-2 outline-offset-2 outline-ring` (or `ring-2 ring-ring`), solid, not `/50` |

### 11.3 Text

| Token | Value | Status | Use |
|---|---|---|---|
| `fg` | `#FFFFFF` | keep | Primary text |
| `fg-secondary` | `#9B9CA0` | keep | Secondary text **and placeholders** (shadcn already does this; 6.0:1) |
| `fg-disabled` | `#71717A` | keep | Disabled only (exempt from contrast) |
| `on-brand` | `#FFFFFF` | **new** | Text and icons on gradients, `brand-strong`, `danger-fill`, platform fills and avatars. Replaces 108 `text-white` (and `/75`, `/80`, `/90` as `on-brand/NN`). `--primary-foreground` → on-brand. |

### 11.4 Brand

| Token | Value | Status | Use |
|---|---|---|---|
| `brand` | `#567FF8` | keep | Non-text only: focus, dots, bars, switch, chart series, decor end. Never behind text. |
| `brand-strong` | `#4467E6` | **new name** (today's gradient end; 4.85:1 with white) | Solid brand fills with text: the platform switch's active segment, the skip link, selection badges. `--primary` → brand-strong. Clerk `colorPrimary`. |
| `brand-deep` | `#20338A` | keep | Gradient start |
| `brand-fg` | `#9DB5FF` | keep | Brand text and icons, links, active segment text, AI labels |
| `brand-soft` | 15% brand | keep | Chips, AI pill, selected cards; **also `info`** |
| `brand-line` | 35% brand | keep | Brand borders |
| `shell-1`, `shell-2` | unchanged | keep, scoped | Logo tile and Upgrade only |

### 11.5 Status

| Token | Value | Status | Use |
|---|---|---|---|
| `success`, `warning`, `danger` | unchanged | keep | Icons, borders, dots, chart marks, meter fills; success and warning text are fine (≥ 7:1 on panel) |
| `danger-fg`, `danger-fill` | unchanged | keep | Danger text; danger fill with `on-brand` text |
| `success-soft`, `warning-soft`, `danger-soft` | 15% of the base (today's majority) | **new** | Chips, banners, callouts. Replaces `bg-*/15` and `/10` (about 60 uses) and the spec's "warning soft", "danger soft" and `bg-warn-soft`. |
| `info`, `info-fg`, `info-soft` | aliases of `brand`, `brand-fg`, `brand-soft` | alias | So status code can say "info" |
| `--destructive` | `danger` | keep for borders and rings | Destructive **text** uses `danger-fg` (COL-008) |

Optional: `*-line` at 40% for each status, only if a lint rule bans opacity modifiers. Today
`border-*/40` is already the majority.

### 11.6 Platform, chart and identity

| Token | Value | Status | Use |
|---|---|---|---|
| `instagram`, `whatsapp` | unchanged | keep | Fills and glyphs only, **never text** (COL-002) |
| `facebook` | `#2563EB` | keep | Marketing "later" tile |
| `linkedin` | `#1E40AF` | **retire**, or move into the avatar palette | Only an avatar stop today |
| `chart-positive`, `chart-neutral`, `chart-negative`, `chart-series-1` | aliases of `success`, `fg-secondary`, `danger`, `brand` | alias | Charts (no new hues) |
| `avatar-1…6` (pairs) | Each lighter stop ≥ 4.5:1 with white. From existing values: `brand-deep → brand-strong` (11.0 / 4.85), `shell-1 → shell-2` (6.52 / 12.66), `linkedin → facebook` (8.72 / 5.17), `instagram → danger-fill` (6.04 / 5.47). Plus two non-semantic hues, for example teal `#0F766E` (5.47) and violet `#6D28D9` (7.10). | **new** (identity, not status) | Avatar fallbacks and schedule account rings. Replaces the three failing pairs and the semantic reuse. |

### 11.7 Alias and recipe fixes in `globals.css` and the primitives (no new colours)

- `@theme inline`: add `--color-card-foreground`, `--color-popover-foreground`,
  `--color-secondary-foreground` and `--color-accent-foreground` (COL-009).
- `--primary: var(--color-brand-strong)`; `--primary-foreground: var(--color-on-brand)`;
  `--accent: var(--color-hover)`; `--popover: var(--color-overlay)`.
- Button:
  - Add `primary` (the gradient, plus `hover:brightness-110` or a `hover` overlay pseudo-element,
    plus `active:brightness-95`).
  - Ghost hover → `bg-hover`.
  - Destructive text → `text-danger-fg`.
  - One focus recipe across all primitives.
- After migrating `text-white` and `bg-white/N`, lock the default palette with
  `--color-*: initial;` in `@theme`, keeping `white`/`black` only through `on-brand` and
  `media-scrim`. Then nothing can drift back.

---

## 12. Findings

| ID | Priority | Title |
|---|---|---|
| COL-001 | P1 | White text on solid `brand #567FF8` fails AA (3.63:1) |
| COL-002 | P1 | Platform colours used as text (Instagram 2.73:1) |
| COL-003 | P1 | Focus indicators below 3:1 on segmented controls, cards and 13 fields |
| COL-004 | P1 | Control edges are 1.35:1; unchecked checkboxes are nearly invisible |
| COL-005 | P1 | No visible hover on about 70 primary and 101 ghost buttons |
| COL-006 | P2 | Sidebar group labels at 3.66:1 |
| COL-007 | P2 | Soft status fills aren't tokens; four copies of the tone map |
| COL-008 | P2 | shadcn destructive variants use the icon red as text |
| COL-009 | P2 | Four shadcn foreground utilities generate no CSS |
| COL-010 | P2 | Overlays don't separate: same surface as cards, a 10% scrim, a black drawer |
| COL-011 | P2 | Two input surfaces, two placeholder colours, field ≈ panel |
| COL-012 | P2 | About 200 white/black utilities block D13's light-mode token swap |
| COL-013 | P2 | Gradients: overlapping blues, three meter recipes, gradient dots |
| COL-014 | P2 | Avatar fallbacks fail contrast and borrow status colours |
| COL-015 | P3 | Schedule account colours reuse status and brand tokens |
| COL-016 | P3 | Hover equals selected; three selection-bar styles |
| COL-017 | P3 | Blur where it does nothing |
| COL-018 | P3 | Toasts aren't on the tokens |
| COL-019 | P3 | Token mirrors without a guard |
| COL-020 | P3 | Skeleton default invisible on panel; four disabled recipes |
| COL-021 | P3 | No named chart palette |

### COL-001 · P1 · White text on solid `brand #567FF8` fails AA (3.63:1)

- **Problem.** UX-TOK-02 lists white on `#567FF8` (3.6:1) as a v1 failure and fixed it for the
  gradient. Solid brand fills with white text have come back in four places.
- **Evidence:**
  - `components/inbox/PlatformStrip.tsx:54`: the active segment is `bg-brand text-white`, in
    `text-xs font-medium` (the inbox's main filter, on screen all the time).
  - `lib/clerk-appearance.ts:10-11`: `colorPrimary: "#567FF8"` with
    `colorPrimaryForeground: "#FFFFFF"`. This is Clerk's primary button on sign-in and sign-up.
  - `app/(marketing)/layout.tsx:25`: the skip link.
  - `styles/globals.css:105`: `--primary` = brand with a white foreground, used by
    `ui/button.tsx:11` (default), `ui/badge.tsx:11` and `ui/avatar.tsx:64`. Every default Button
    is overridden today, but any new one fails.
- **Affected files.** `PlatformStrip.tsx`, `clerk-appearance.ts`, `(marketing)/layout.tsx`,
  `globals.css`, `ui/button.tsx`, `ui/badge.tsx`, `ui/avatar.tsx`.
- **Recommendation:**
  1. Add `brand-strong #4467E6` (white 4.85:1, already the gradient's end).
  2. Point `--primary` and Clerk's `colorPrimary` at it.
  3. Use it for the active platform segment and the skip link.
  4. Keep `brand` for non-text marks only, and document that rule in `tokens.ts`.

### COL-002 · P1 · Platform colours used as text (Instagram 2.73:1)

- **Problem.** Platform tokens are brand marks for fills. As text they fail AA.
- **Evidence:**
  - `components/inbox/ThreadHeader.tsx:26, 100`: `PLATFORM_TEXT = { instagram: "text-instagram", … }`
    renders "Instagram" in `text-xs` on the panel header, at **2.73:1**. Every Instagram thread
    shows it. WhatsApp's is 5.00:1.
  - The same colour as a schedule account ring (`lib/schedule/format.ts:92`) is 2.73:1 against
    panel, below 3:1 for non-text.
- **Affected files.** `ThreadHeader.tsx`, `lib/schedule/format.ts`.
- **Recommendation.** Render the platform name in `fg-secondary`, next to the platform glyph or
  dot, which carries the colour. Record "platform colours: fills and glyphs only" in the token
  docs. For rings, see COL-015.

### COL-003 · P1 · Focus indicators below 3:1 on segmented controls, cards and 13 fields

- **Problem.** There are three focus recipes. The global one (`globals.css:127`: a 2 px brand
  outline, offset 2 px) passes everywhere (4.54:1 on panel). The others don't.
- **Evidence:**
  - **`ring-3 ring-ring/50` as the only cue: 2.10:1 on panel.**
    - Primitives: `ui/tabs.tsx:27` (8 TabsTriggers) and `ui/toggle-group.tsx:37` (31 items; with the tabs, in
      23 files).
    - Custom elements: `AutomationEditor.tsx:253`, `AutomationRow.tsx:177`,
      `AutomationsPage.tsx:319`, `StepCard.tsx:45`, `PostsStep.tsx:215, 254`,
      `CommentComposer.tsx:91`, `PostCard.tsx:38`, `MediaTray.tsx:206`, `composer/Section.tsx:29`,
      `MetricTile.tsx:70`, `PriorityQueue.tsx:105`, `TopPostsCard.tsx:45, 59`.
    - Button, Input, Select, Checkbox and Switch add a 1 px solid `border-ring`, which passes,
      but thinly.
  - **`outline-none focus:bg-raised` as the only cue: 1.17:1.** 13 fields in 10 files:
    - `ListHeader.tsx:142` (inbox search)
    - `MediaLibraryDialog.tsx:88, 101`
    - `PostPreview.tsx:139`
    - `EmojiPicker.tsx:101`
    - `ScheduledList.tsx:227`
    - `ScheduleFields.tsx:79` (2 fields)
    - `TemplatePicker.tsx:117`
    - `HashtagGroupsDialog.tsx:219, 247`
    - `ListView.tsx:326`
    - `PostingTimesDrawer.tsx:275`

    UX-INB-03 itself prescribes `focus:bg-raised` for the search box.
  - **Inbox composer:** focus changes the border from white/10 to white/20, which is 1.42:1
    (`Composer.tsx:292`). Ask's composer uses `ring-ring/40` (`AskComposer.tsx:87`).
- **Affected files.** `ui/tabs.tsx`, `ui/toggle-group.tsx`, `ui/button.tsx`, `ui/input.tsx`,
  `ui/select.tsx`, `ui/textarea.tsx`, `ui/checkbox.tsx`, `ui/switch.tsx`, plus the roughly
  25 files listed above.
- **Recommendation.**
  - Use one recipe everywhere: a solid `ring` (brand) at 2 px, as an outline or ring with a 2 px
    offset. It reaches at least 3.96:1 on every surface.
  - Delete `ring-ring/50` and `/40`.
  - Keep `focus:bg-raised` as an extra cue, never as the only one.
  - Update UX-INB-03's wording.

### COL-004 · P1 · Control edges are 1.35:1; unchecked checkboxes are nearly invisible

- **Problem.** UX-A11Y-01 requires "icons and control borders ≥ 3:1". Every control edge is
  `line` or `input` (white at 10%), which is 1.35:1 against panel and 1.32:1 for a field on
  panel. The spec contradicts itself here: UX-INB-03 and UX-INB-07 prescribe `border-line` for
  inputs.
- **Evidence:**
  - `ui/checkbox.tsx:16`: `border-input dark:bg-input/30` makes the unchecked box a
    1.35:1 outline. It's used for bulk select (`AutomationRow.tsx`), `SourceSheet.tsx`,
    `ListView.tsx` and `PostingTimesDrawer.tsx`.
  - The edges of `ui/input.tsx:10`, `ui/select.tsx:46`, `ui/textarea.tsx:9` and about 20 raw
    inputs.
  - The switch's off track is 1.27:1, but its white thumb (16:1) carries the state, so the
    switch is acceptable.
- **Affected files.** `ui/checkbox.tsx`, `ui/input.tsx`, `ui/select.tsx`, `ui/textarea.tsx`,
  raw inputs (see COL-003).
- **Recommendation.**
  - Add `line-control #6B6B6B` (3.09:1 on panel, 3.94:1 on canvas).
  - **Minimum:** checkbox and radio edges, which have no other cue.
  - **Owner decision:** text-input edges. Labels already identify the inputs, so WCAG allows
    hairlines there, but the spec doesn't. Either raise the edges or amend UX-A11Y-01 to exclude
    labelled text fields. Record the choice in CONFLICTS.md.

### COL-005 · P1 · No visible hover on about 70 primary and 101 ghost buttons

- **Problem.** The two most common button styles give no hover feedback, and hover is written
  six different ways.
- **Evidence:**
  - **Gradient primary buttons.** `cn(buttonVariants(), "bg-brand-gradient text-white")` keeps
    `hover:bg-primary/80` (checked with the project's `cn`). The compiled rule sets
    `background-color` under the gradient image, so nothing changes. That covers 54 `<Button>`s
    and about 12 hand-rolled controls, including Send (`Composer.tsx:414`). Only 3 have
    `hover:brightness-110`.
  - **Ghost buttons.** `ui/button.tsx:17`: `dark:hover:bg-muted/50` is `field` at 50%, which is
    `#1E1E1E` on panel (1.01:1). 101 ghost Buttons have no hover override. For 92 of them the
    resting text is already `fg`, so `hover:text-foreground` changes nothing either. Example:
    "Start a new thread" (`AskConversation.tsx:171`).
  - **Outline.** 14 `AlertDialogCancel`: `#262626 → #2A2A2A` (1.04:1).
  - **Six hover recipes:** `hover:bg-white/5` (25), `hover:bg-white/10` (12), `hover:bg-raised`
    (15), `dark:hover:bg-muted/50`, `hover:bg-[color-mix(…)]`, `hover:brightness-110` (3).
- **Affected files.** `ui/button.tsx`, the 52 files with `bg-brand-gradient`, and every ghost
  call site.
- **Recommendation.**
  - Add `hover` and `pressed` tokens (§11.1).
  - Give Button a `primary` variant: the gradient, `hover:brightness-110`,
    `active:brightness-95`, `disabled:opacity-50`. Replace the className overrides.
  - Set ghost and outline hover to `bg-hover`, with `aria-expanded:bg-pressed`.

### COL-006 · P2 · Sidebar group labels at 3.66:1

- **Problem.** The "ENGAGE" and "GROW" labels are 11 px uppercase in `text-fg-secondary/70`,
  which is 3.66:1 on panel. They appear on every app page.
- **Evidence.** `components/shell/AppSidebar.tsx:257`. `fg-secondary/70` is the only opacity
  modifier on a text token in the codebase.
- **Affected files.** `AppSidebar.tsx`.
- **Recommendation.** Use `text-fg-secondary` (6.01:1). The labels' weight and spacing already
  set them apart.

### COL-007 · P2 · Soft status fills aren't tokens; four copies of the tone map

- **Problem.** The spec names "warning soft", "danger soft" and `bg-warn-soft`
  (UX-SH-04, UX-INB-04, UX-SCR-03), but only `brand-soft` exists. Code builds the rest with
  opacity modifiers, and they have drifted.
- **Evidence:**
  - **Danger soft:** `/15` ×12, `/10` ×8, `destructive/10` ×3, `/20` ×5, `/30` ×1.
  - **Warning:** `/15` ×20, `/10` ×4. **Success:** `/15` ×13, `/10` ×3.
  - **Neutral chip:** `bg-white/5` in three maps, `bg-white/10` in Billing (4.45:1).
  - **The tone→class map is copied 4 times:** `lib/inbox/format.ts:70-76`,
    `lib/schedule/format.ts:38-44`, `billing/BillingPage.tsx:63-68`,
    `marketing/InboxPreview.tsx:24-28`.
  - **More partial maps:** `agent/RunView.tsx:194-195`, `automations/RunsPane.tsx:26`,
    `billing/PaymentHistory.tsx:18`, `lib/publishing/rules.ts:251`,
    `connections/AccountCard.tsx:23-27`.
- **Affected files.** All of the above, plus about 20 inline `bg-*/10` and `/15` sites.
- **Recommendation.**
  - Add `success-soft`, `warning-soft` and `danger-soft` at 15%, plus an `info` alias.
  - Keep one `TONE_CLASS` (in `lib/`) and import it everywhere.
  - Neutral chips use `bg-hover`.

### COL-008 · P2 · shadcn destructive variants use the icon red as text

- **Problem.** `--destructive` maps to `danger`, the icon and border red. shadcn's variants use
  it as text. Our own code uses `danger-fg` for text correctly 121 times.
- **Evidence:**
  - `billing/BillingPage.tsx:315`: `AlertDialogAction variant="destructive"` ("Cancel plan").
    Its text is `#EF4444` on `destructive/20`, which is **3.51:1**.
  - `schedule/post-parts.tsx:227`: `DropdownMenuItem variant="destructive"` ("Delete") is
    **4.38:1** on the popover and 3.51:1 when highlighted.
  - The variant definitions: `ui/button.tsx:19`, `ui/badge.tsx:15`, `ui/dropdown-menu.tsx:75`.
- **Affected files.** `ui/button.tsx`, `ui/badge.tsx`, `ui/dropdown-menu.tsx`, `BillingPage.tsx`,
  `post-parts.tsx`.
- **Recommendation.**
  - In the three variants, set destructive text to `text-danger-fg` and the fill to
    `bg-danger-soft`.
  - Or make the destructive button a filled `bg-danger-fill text-on-brand`, matching the
    12 existing hand-written danger buttons, and remove those overrides.

### COL-009 · P2 · Four shadcn foreground utilities generate no CSS

- **Problem.** This is the bug class UX-TOK-01 calls out from v1: utilities that don't exist.
- **Evidence.** `globals.css:113-121` doesn't map `--card-foreground`, `--popover-foreground`,
  `--secondary-foreground` or `--accent-foreground`. A Tailwind 4.3.3 compile of the worktree
  emits no rule for these classes or their variants:
  - `text-popover-foreground` (7 uses)
  - `text-accent-foreground` and variants (12)
  - `text-secondary-foreground` (3)
  - `aria-expanded:`, `data-open:`, `focus:**:` and `group-focus/…` variants

  It's harmless today, because the text inherits `fg` (white). But menu focus rules such as
  `not-data-[variant=destructive]:focus:**:text-accent-foreground` silently do nothing.
- **Affected files.** `globals.css`; consumers in `ui/dialog`, `alert-dialog`, `sheet`,
  `popover`, `dropdown-menu`, `select` and `button`.
- **Recommendation.** Add the four `--color-*-foreground` lines to `@theme inline`. Extend
  `tokens.test.ts` so that every `--<name>` in `:root` has a `--color-<name>` mapping.

### COL-010 · P2 · Overlays don't separate: same surface as cards, a 10% scrim, a black drawer

- **Problem.** Elevation doesn't read in dark mode (§6), and scrims are inconsistent.
- **Evidence:**
  - Popover, menu, dialog and sheet surfaces are `--popover` (panel), the same as cards
    (1.00:1). 54 call sites set `bg-panel` (21 add `shadow-xl`), and the black shadow is
    invisible on near-black.
  - shadcn scrims are `bg-black/10` + `backdrop-blur-xs` (`ui/dialog.tsx:42`,
    `ui/alert-dialog.tsx:39`, `ui/sheet.tsx:40`): 1.00:1 over canvas.
  - Custom overlays use `bg-black/60` (`AskPanel.tsx:82`, `AgentSettingsPage.tsx:394`), and so
    do Clerk (`clerk-appearance.ts:24`) and the spec (UX-SH-02).
  - The mobile drawer is `bg-canvas` (`MobileNav.tsx:39`). It is black over black behind a 10%
    scrim, while the desktop sidebar is `panel`.
- **Affected files.** `ui/dialog.tsx`, `ui/alert-dialog.tsx`, `ui/sheet.tsx`, `ui/popover.tsx`,
  `ui/dropdown-menu.tsx`, `ui/select.tsx`, `MobileNav.tsx`, and the overlay call sites.
- **Recommendation.**
  - Add a `scrim` token at 60% black and use it in the three primitives; drop the blur.
  - Add an `overlay` surface (`#262626`) for `--popover`, and remove the per-call-site
    `bg-panel` overrides.
  - Make the drawer `bg-panel`, like the sidebar.

### COL-011 · P2 · Two input surfaces, two placeholder colours, field ≈ panel

- **Problem.** Inputs look different depending on which component built them, and on a card
  their fill is invisible anyway.
- **Evidence:**
  - **Input and SelectTrigger** (`ui/input.tsx:10`, `ui/select.tsx:46`): `bg-transparent
    dark:bg-input/30`, which is `#262626` on panel. That's 24 Inputs and 14 Select triggers.
  - **Textarea and raw inputs** (`ui/textarea.tsx:9` and about 20 raw inputs): `bg-field`,
    `#1D1D1D`. Both kinds appear in the same forms, for example `SourceSheet.tsx`.
  - **Field vs panel** is 1.02:1 (ΔE00 0.63).
  - **Placeholders.** The base `::placeholder` is `fg-disabled` (`globals.css:128`), at
    **3.41:1** on panel and 3.49:1 on field. Raw inputs use it, and so do
    `data-deletion/page.tsx:108` and `PhraseChips.tsx:86`. shadcn inputs use
    `muted-foreground` (6.0:1).
- **Affected files.** `ui/input.tsx`, `ui/select.tsx`, `ui/textarea.tsx`, `globals.css`, raw
  inputs.
- **Recommendation.**
  - Put every input on `field` and make its edge identify it (COL-004).
  - Set the base `::placeholder` to `fg-secondary`, as shadcn already does.
  - Restrict `fg-disabled` to disabled controls.

### COL-012 · P2 · About 200 white/black utilities block D13's light-mode token swap

- **Problem.** D13 promises light mode as "a token swap later", but much of the colour is
  outside the tokens.
- **Evidence:**
  - **Fixed values that won't flip:** 108 `text-white`, about 80 `bg-white/N` (plus
    `border-`, `ring-` and `stroke-white/N`), 15 `black` utilities.
  - **Literals in the CSS:** `--primary-foreground: #FFFFFF` (`globals.css:105`) and hex stops
    inside the `@utility` gradients (`globals.css:51-53`).
  - **Nothing stops drift.** The default Tailwind palette is still enabled (there's no
    `--color-*: initial`), so `bg-red-500` would compile without complaint.
- **Affected files.** 100 files (§4.3), plus `globals.css`.
- **Recommendation.**
  - Add `on-brand`, `hover`, `pressed`, `scrim` and `media-scrim` (§11).
  - Migrate the utilities mechanically. `text-white` next to a gradient or fill becomes
    `text-on-brand`, `bg-white/5` becomes `bg-hover`, and so on.
  - Write the gradient stops as `var()`.
  - Then lock the palette with `--color-*: initial`.

### COL-013 · P2 · Gradients: overlapping blues, three meter recipes, gradient dots

- **Problem.** Gradients aren't a controlled system (§9).
- **Evidence:**
  - **Two blue gradients:** `bg-shell-gradient` (`#3352CC → #1C2D70`, light to dark) and
    `bg-brand-gradient` (`#20338A → #4467E6`, dark to light). Their dark stops are ΔE00 4.3
    apart.
  - **Shell used beyond UX-SH-01:** `BillingPage.tsx:274`, `PreviewPane.tsx:77`,
    `FinalCta.tsx:12`.
  - **Gradient on 8 px unread dots** (`NotificationsButton.tsx:39, 122`), while the row's unread
    dot is solid `bg-brand` (`ConversationRow.tsx:98`).
  - **AI-credit meter drawn two ways:** solid `bg-brand` on `bg-white/10` in the sidebar
    (`UsageCard.tsx:11, 93`) and the decor gradient on `bg-raised` in Billing
    (`UsageMeter.tsx:19-23`, `BillingPage.tsx:94-97`). The publish-limit meter is `bg-brand` on
    `bg-field` (`ScheduleRail.tsx:117`).
  - **The FILL map is duplicated:** `UsageMeter.tsx:19` and `BillingPage.tsx:94`.
- **Affected files.** `globals.css`, `tokens.ts`, `tokens.test.ts`, and the files above.
- **Recommendation.**
  - Adopt the four-gradient system in §9, with `var()` stops.
  - Scope the shell gradient to the logo and Upgrade.
  - Draw marks under 12 px solid.
  - Use one meter component everywhere: decor fill on a `raised` track, warning at 80%,
    danger at 100%.

### COL-014 · P2 · Avatar fallbacks fail contrast and borrow status colours

- **Problem.** Three of the six avatar gradients put a white initial (16–18 px semibold, so
  4.5:1 applies) on light orange or green. They also turn customers into "warning" or "danger"
  colours.
- **Evidence.** `lib/inbox/format.ts:185-192` (rendered in `ContactAvatar.tsx:40`):
  - `from-instagram to-warning`: midpoint 3.84:1, light end 2.26:1
  - `from-whatsapp to-success`: midpoint 2.73:1, end 2.28:1
  - `from-danger-fill to-warning`: midpoint 3.54:1, end 2.26:1
  - `from-brand-deep to-brand`: light corner 3.63:1

  `linkedin` exists only for pair 6.
- **Affected files.** `lib/inbox/format.ts`, `ContactAvatar.tsx`.
- **Recommendation.** Use a separate identity palette, `avatar-1…6`, where every stop is at
  least 4.5:1 against white (candidates in §11.6). Share it with the schedule account colours
  (COL-015).

### COL-015 · P3 · Schedule account colours reuse status and brand tokens

- **Problem.** Account identity uses tokens that already mean something else.
- **Evidence.** `lib/schedule/format.ts:92-93`: `RINGS` and `DOTS` are brand, instagram,
  **warning**, whatsapp, **brand-fg** and fg-secondary.
  - An orange ring reads as a warning.
  - `brand` and `brand-fg` are the same hue (1.81:1 between them).
  - The `instagram` ring is 2.73:1 against panel.
  - Under protanopia, `whatsapp` and `warning` are ΔE76 9.2 apart.
- **Affected files.** `lib/schedule/format.ts`, and the schedule cards and filter.
- **Recommendation.** Use the avatar identity palette (COL-014), and keep the account name or
  avatar beside every ring. That already happens in the filter.

### COL-016 · P3 · Hover equals selected; three selection-bar styles

- **Problem.** On panel, a hovered row and the selected row are the same colour. Selection is
  also marked three different ways.
- **Evidence:**
  - `bg-white/5` on panel is `#2A2A2A`, which equals `raised` (ΔE00 0.06):
    `ConversationRow.tsx:63-65` and `sidebar-styles.ts:11-13`.
  - The brand bar is 3 px (`ConversationRow.tsx:68`), 2 px via `before:` (`sidebar-styles.ts:13`),
    or a 2 px inset shadow (`Threads.tsx:183`).
  - Segmented controls in the same inbox header use three active looks:
    - `bg-brand` with white (`PlatformStrip.tsx:54`)
    - `bg-raised text-fg` (`ListHeader.tsx:103`)
    - `bg-raised text-brand-fg` (`ui/toggle-group.tsx:37`, `ui/tabs.tsx:27`, as spec'd)
- **Affected files.** `ConversationRow.tsx`, `sidebar-styles.ts`, `Threads.tsx`,
  `PlatformStrip.tsx`, `ListHeader.tsx`.
- **Recommendation.**
  - Keep hover at the `hover` overlay and selected at `raised` plus a bar. They're
    distinguishable once the bar is consistent, so standardise one bar width (2 px).
  - Give all segmented controls the ToggleGroup look. For PlatformStrip, keep the coloured look
    if the owner wants it (C-063), but use `brand-strong` (COL-001).

### COL-017 · P3 · Blur where it does nothing

- **Problem.** Some blur adds rendering cost with no visible effect.
- **Evidence:**
  - `settings/SaveBar.tsx:70`: `bg-panel/95 backdrop-blur` on a sticky bar. Blur behind a 95%
    opaque surface isn't visible, but it re-composites on every scroll frame.
  - shadcn overlays blur the whole viewport (`backdrop-blur-xs`) to compensate for a 10% scrim
    (COL-010).
  - `marketing/SiteHeader.tsx:13` is intentional and fine.
- **Affected files.** `SaveBar.tsx`, `ui/dialog.tsx`, `ui/alert-dialog.tsx`, `ui/sheet.tsx`.
- **Recommendation.** Make the SaveBar opaque `bg-panel`. Replace the overlay blur with the 60%
  `scrim`.

### COL-018 · P3 · Toasts aren't on the tokens

- **Problem.** Toasts use sonner's own dark palette rather than ours.
- **Evidence.** `app/layout.tsx:34` uses `<Toaster theme="dark" />`. Sonner's dark theme is
  `--normal-bg: #000` and `--normal-border: hsl(0 0% 20%)`, so toasts are a black box on the
  black canvas. It also has its own success, info, warning and error hues (unused, since
  `richColors` is off).
- **Affected files.** `app/layout.tsx`.
- **Recommendation.** Set sonner's variables, through `toastOptions`/`style` or a scoped CSS
  block, to `overlay`, `line-strong` and `fg`, so toasts follow the overlay surface.

### COL-019 · P3 · Token mirrors without a guard

- **Problem.** Literal copies of tokens are justified, but nothing checks that they stay equal
  to the tokens.
- **Evidence:**
  - `lib/clerk-appearance.ts:10-24`: 13 hex values and 2 `rgb()` values. Clerk can't read
    variables.
  - `components/marketing/og.tsx:7-16`: 10 hex values and 1 `rgba` glow. Satori can't read
    variables.
  - `app/manifest.ts:17-18` and `app/layout.tsx:20`: `#000000`.
  - `marketing/primitives.tsx:12-15`: SVG `#fff` and `#20338A`.

  `tokens.test.ts` checks only `globals.css`.
- **Affected files.** The four above, plus `tokens.test.ts`.
- **Recommendation.**
  - Import the values from `styles/tokens.ts`, adding a `hex` lookup there, or extend the test to
    compare these objects with `colorTokens`.
  - Draw the logo SVG with `currentColor` and classes.

### COL-020 · P3 · Skeleton default invisible on panel; four disabled recipes

- **Problem.** The Skeleton's default colour doesn't work on cards, and disabled states are
  styled four ways.
- **Evidence:**
  - `ui/skeleton.tsx:7` uses `bg-muted` (`field`), 1.02:1 on panel. 114 of 117 Skeleton uses
    override it: `bg-raised` ×107 and `bg-panel` ×7.
  - **Disabled recipes:**
    - `disabled:opacity-50` (10) and `data-disabled:opacity-50` (5)
    - `disabled:opacity-60` (4)
    - `bg-raised text-fg-disabled` (send buttons: `Composer.tsx:415`, `AskComposer.tsx:119`)
    - `fg-disabled` used only 8 times
- **Affected files.** `ui/skeleton.tsx`, the primitives, `Composer.tsx`, `AskComposer.tsx`.
- **Recommendation.**
  - Make the Skeleton default `bg-raised`.
  - Use one disabled rule: `opacity-50` for every control, including the send buttons, which
    then keep their gradient at half opacity. Or `bg-raised text-fg-disabled` everywhere. Pick
    one and document it.

### COL-021 · P3 · No named chart palette

- **Problem.** Status charts are correct but unnamed. Categorical colours are improvised.
- **Evidence.**
  - Status charts use the right tokens: `StatsPane.tsx:135-172`, `SentimentBar.tsx:4-8`,
    `SentimentCard.tsx:7-11`, `TrendLine.tsx:29`.
  - The deuteranopia margin for success vs danger is ΔE76 13.6; the legends carry numbers.
  - The decor meter's start stop is 1.30:1 against its track; the value is also in text.
  - Categorical colours (accounts, avatars) borrow status and platform tokens.
- **Affected files.** The chart components and `lib/schedule/format.ts`.
- **Recommendation.**
  - Add `chart-*` aliases (§11.6) with no new hues.
  - Keep the "legend plus numbers plus sr-only table" pattern from `StatsPane` as the standard.
  - Use the identity palette for categorical series.

---

## Appendix: what is already right (keep)

- **Token discipline.** About 90% of colour usages are tokens. No colours leaked from the
  mockups. The hex values are justified mirrors.
- **`tokens.ts`, `tokens.test.ts` and `/dev/tokens`.** The palette, its documentation and its
  test all come from one list.
- **The danger trio.** `danger` for icons, `danger-fg` for text (121 correct uses),
  `danger-fill` for fills with white (5.47:1).
- **UX-TOK-02's fixes hold** wherever the tokens are used: `fg-secondary` is 6.01:1 on panel,
  `brand-fg` 7.17:1 on raised, and gradient text 4.85:1.
- **The global `:focus-visible` outline** (`globals.css:127`) passes on every surface. Its
  comment explains why it's in the base layer.
- **Reduced motion** is respected by both animated colour utilities (`automation-line-active`,
  `text-shimmer`).
- **The automation stats chart** (colour plus legend plus table) is the accessible chart pattern
  to copy.
