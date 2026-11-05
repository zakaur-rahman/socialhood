# Theme: where the values live and how to change them

How the look of the web app is wired, so that one edit reaches every screen, and what to do when
you want to change it. The rules for using the tokens are in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md);
this page is about the machinery and the knobs. Decisions: CONFLICTS C-127, and C-177 for today's plain
solid look.

---

## 1. Architecture

### One place for values

`apps/web/src/styles/globals.css` is the only place a theme value is written: colours, shadows,
type sizes, tracking, radii, easings, breakpoints, durations and gradients. Nothing else repeats a
value.

```
globals.css  ──(pnpm tokens: scripts/gen-tokens.mjs)──►  tokens.generated.ts / .json
     │                                                         │
     │ Tailwind reads @theme, makes the classes                │ read by
     ▼                                                         ▼
bg-panel, text-fg-secondary, shadow-floating …      tokens.ts (descriptions + type roles) ─► /dev/tokens
                                                colorValue() ─► Clerk, OG image, manifest, viewport,
                                                                 global-error page
                                                generate-icons.mjs reads the .json for the icon colours
```

- **`@theme { … }`** declares the tokens. Tailwind turns `--color-panel` into `bg-panel`,
  `border-panel`, `text-panel` …, `--shadow-floating` into `shadow-floating`, `--radius-xl` into
  `rounded-xl`, `--tracking-eyebrow` into `tracking-eyebrow`. The first line, `--color-*: initial;`,
  switches off Tailwind's default colours (the palette lock, C-075): `bg-red-500` or `bg-surface`
  generates no CSS, and the design lint names it.
- **`:root { … }`** holds what is not a Tailwind theme key: the motion durations (`--motion-*`), the
  gradients as variables (`--gradient-shell` …), and the shadcn aliases.
- **`@utility`** rules make the Instagram logo gradient and a few helpers (`bg-instagram-logo-gradient`,
  `mask-fade-x`, `duration-fast`, `mark-forced`, `selected-forced`).
- **`@theme inline`** exposes the shadcn aliases as colours (`--color-popover: var(--popover)`).
  The `:root` aliases and this block exist only so that `shadcn add` output, which is written in
  `bg-popover` and `text-muted-foreground`, still compiles and lands on the tokens. Hand-written
  code, `components/ui` included, uses the token names (`bg-overlay`, `text-fg-secondary`,
  `border-line-control`, `outline-brand`); the lint refuses the alias names in source.
- **`pnpm tokens`** (it also runs before `pnpm dev` and `pnpm build`) parses globals.css and writes
  `tokens.generated.ts` and `tokens.generated.json`. They are committed. `tokens.test.ts` regenerates
  from globals.css in memory and fails if the committed files differ, so an edit that skipped
  `pnpm tokens` can't land.
- **`tokens.ts`** keeps what is not a value: each colour's name, what it is for, its swatch class,
  and the type-role constants (`EYEBROW`, `PAGE_TITLE` …). The test requires a description for every
  `--color-*` and rejects one for a token that no longer exists.
- **Consumers that can't use CSS variables** call `colorValue("brand-strong")` (or `radiusValue("lg")`):
  Clerk (it computes shades), the OG image (Satori), the manifest, the viewport `themeColor`, and the
  global error page (the stylesheet isn't loaded there). Clerk's element styles are plain CSS, so
  they use the variables, `var(--radius-xl)` included.
- **tailwind-merge** (`lib/utils.ts`) is taught the custom names (`shadow-glow*`, `shadow-surface`,
  `tracking-eyebrow`, `leading-display`, `duration-*`, `ease-*`) so `cn()` merges them like Tailwind's
  own. A new utility that replaces another of its kind needs a line there.

### Two themes (C-129)

Dark is the default; Light is a choice. A colour that differs between themes is written once in
`@theme` as `light-dark(LIGHT, DARK)` (light first), and the browser picks by the element's
`color-scheme`:

- `<html data-theme="dark|light|system">` sets it (`:root`, `:root[data-theme=light]`,
  `:root[data-theme=system]` in globals.css). System sets both schemes, so the OS decides with no script and
  no listener.
- A subtree can pin itself: `.site` sets `color-scheme: light`, which keeps the public site on its paper in a
  dark app. `<html>` is pinned too (an inline script on a first load, `ThemePin` on a client
  navigation), so scrollbars, overscroll and portals match.
- Components never need a per-theme class; the lint still refuses `dark:`.
- A colour with one value (a platform brand, `media-scrim`, `on-brand`, `brand-strong`, `brand-deep`,
  `shell-*`, `danger-fill`) is the same in both and is listed in `themeInvariant` (`tokens.ts`) with a
  reason. Shades are `color-mix` of a base token and follow it. `tokens.test.ts` fails on any other single
  literal, on a pair whose two sides are equal, and on a listed invariant that is now a pair.
- `pnpm tokens` splits the pairs: `colors`/`shadows` are the dark values, `colorsLight`/`shadowsLight` the
  light ones. `colorValue(name, theme)` reads either (dark by default).

How the choice is kept (`lib/theme.ts`): the cookie `sh_theme` (`dark` | `light` | `system`, a year,
`path=/`, `SameSite=Lax`, not HttpOnly). A script in `<head>` copies it to `data-theme` before first paint.
It is a script and not a server read because the root layout is shared with the static, hourly-revalidated
marketing pages and `cookies()` would make them dynamic; the CSP already allows inline scripts. The switch
(`ThemeSwitch`, `useTheme`) writes the cookie and the attribute at once. It is in Settings → Appearance and in
the workspace menu. `ThemeSync` keeps `<meta name="theme-color">` on the canvas of the theme on screen.

Consumers that can't use CSS variables:

| Consumer | In Light |
|---|---|
| Clerk (`lib/clerk-appearance.ts`) | `clerkAppearanceFor(theme)`: Light drops the dark base and reads the light variables; the sign-in and sign-up cards and the user button pass the set for the theme on screen (`components/auth/ThemedClerk.tsx`). Element styles are CSS variables and follow by themselves. |
| Viewport `themeColor` | Dark canvas from the server; `ThemeSync` sets it per theme |
| `statusBarStyle` | Stays `black` (iOS reads it once at launch) |
| Manifest | Dark on purpose (the installed app opens on the default) |
| OG image | The public site's paper, with the logo |
| Logo and icons | The same gradient tile in both themes. Locked: business verification uses them |
| Global error page | Dark: the stylesheet isn't loaded, the theme is unknown |
| Sonner | Follows with no `theme` prop: every toast colour is a token class |
| Avatar edge | A `line` ring, no blend mode |

Light values, measured (WCAG): `fg` on panel 18.0, `fg-secondary` 5.05 (raised-hover) to 6.58 (panel),
`line-control` 3.61 to 3.91, `brand` marks 4.04 to 5.25, `brand-fg` 5.71 to 7.43, `brand-strong` with white 5.82,
status text on its soft fill 4.9 or more, `danger-fg` 4.31 or more. `styles/contrast.test.ts` holds the key pairs
of both themes.

The emails (`apps/api/.../notify/templates/layout.py`) are a separate, light palette on purpose.

---

## 2. The tokens

Where a row says "(shade)", the value is derived from another token with `color-mix`, so changing
the base changes the shade.

### Surfaces

| Token | Controls |
|---|---|
| `canvas` | App and thread background, the page behind everything |
| `panel` | Cards, sidebar, list pane, headers, composer bar, phone drawer; solid |
| `field` | Incoming bubbles, the segmented track, composer shells, quiet insets (`CardInset`), dialog footers |
| `field-input` | Text fields and select triggers: white on light, the same as `field` on dark |
| `raised` | Selected row, chosen chip, focused input, secondary button |
| `segment` | The chosen segment or tab, on its `field` track: white on light, the same as `raised` on dark |
| `raised-hover` | Hover on raised surfaces |
| `overlay` | What floats: popovers, menus, select options, dialogs, sheets, toasts |
| `canvas-veil` (shade) | A dimmed cell or inset: days outside the month, a card in a flow |
| `panel-glass`, `panel-veil` (shades) | A marketing card's quieter fill; the floating marketing nav |

### States

| Token | Controls |
|---|---|
| `hover` | Hover fill on any surface, the neutral chip fill |
| `pressed` | Pressed or open (`aria-expanded`, `data-state=open`); hover on an already-filled `hover` surface |
| `scrim` | Modal and drawer backdrop |
| `media-scrim` | Black over photos and video; the base of the three steps |
| `media-wash`, `media-chip`, `media-heavy` (shades) | 20% light dim, 70% label or button on a photo, 85% text over a photo |

### Text

| Token | Controls |
|---|---|
| `fg` | Primary text and icons; the fill of the inverse button |
| `fg-secondary` | Secondary and meta text, placeholders |
| `fg-disabled` | Disabled controls only |
| `fg-hover` (shade) | Hover on the inverse button |
| `on-brand` | Text and icons on `brand-strong`, `danger-fill`, platform fills |
| `on-brand-soft`, `on-brand-line`, `on-brand-line-strong` (shades) | Quiet fill and edges on a brand bubble |

### Lines

| Token | Controls |
|---|---|
| `line` | Where a line means something: tables, rows, pane edges, a secondary button's edge. The default border colour |
| `line-card` | A card's thin edge |
| `line-subtle` | Row dividers inside a card |
| `line-strong` | Outline buttons, a chosen chip or the current plan's edge, the chart axis |
| `line-control` | Edges that identify a control (fields, selects, checkboxes, switches), 3:1 on every surface |

### Brand

| Token | Controls |
|---|---|
| `brand` | Non-text marks: focus outline, dots, selection bar, switch on, chart series |
| `brand-strong` | The accent fill: main buttons, outgoing bubbles; Clerk's primary |
| `brand-deep` | The logo's bars and an identity stop |
| `brand-fg` | Brand-coloured text and icons on dark |
| `brand-soft`, `brand-soft-hover` | Soft brand fills (info tone, soft button) and their hover |
| `brand-line` | Brand borders |
| `shell-1`, `shell-2` | The logo tile, the app icons, the share image, one identity pair. Locked: business verification uses them |

### Status

| Token | Controls |
|---|---|
| `success`, `warning`, `danger` | Status marks and text on soft fills |
| `danger-fg` | Danger text on dark |
| `danger-fill`, `danger-fill-hover` (shade) | Failed bubble, the destructive button |
| `success-soft`, `warning-soft`, `danger-soft` | Chip, banner and callout fills |
| `danger-line`, `warning-line` (shades) | Callout edges |

### Platform and chart

| Token | Controls |
|---|---|
| `instagram`, `whatsapp`, `facebook`, `linkedin` | Third-party brand fills and glyphs, never text |
| `chart-positive`, `chart-neutral`, `chart-negative`, `chart-series-1` | Aliases of `success`, `fg-secondary`, `danger`, `brand`: every bar, dot and legend of that series |

Categorical series (accounts, people) use the identity palette in `lib/ui/identity.ts`, which is
made of the tokens above.

### Gradients

The app's fills are solid. What's left (DESIGN_SYSTEM §1.9):

| Variable and utility | Controls |
|---|---|
| `--gradient-instagram-logo`, `bg-instagram-logo-gradient` | Instagram's logo tile; never under text |
| `--gradient-shell` | The logo tile only (`[data-logo-mark]`) |
| `--gradient-media-fade` | The fade over a photo |

### Shadows

| Token | Controls |
|---|---|
| `shadow-floating` | Level 1: popovers, menus, select options, toasts |
| `shadow-overlay` | Level 2: dialogs, alert dialogs, sheets over the scrim |
| `shadow-surface` | Cards: a top highlight and a soft drop |
| `shadow-glow`, `shadow-glow-hover`, `shadow-glow-button` | Marketing: brand-tinted drops under cards, card hover, the primary call to action; never in the app |
| `shadow-site-card`, `shadow-site-button-primary`, `shadow-site-button-secondary` | The public site's own card and button shadows |
| `shadow-crop-mask` (utility) | The crop box's dimming spread; not an elevation |

### Radius

`--radius-sm` 0.25rem (checkbox, tags), `-md` 0.375rem (small buttons, tooltips), `-lg` 0.5rem
(inputs, buttons, menus), `-xl` 0.75rem (cards, dialogs), `-2xl` 1rem (marketing cards). Clerk and
the global error page read these too.

### Type

| Token | Controls |
|---|---|
| `--text-2xs` 11/16, `--text-md` 15/24 | The two sizes the Tailwind scale lacks |
| `--tracking-eyebrow` 0.08em | Eyebrows only (the `EYEBROW` role) |
| `--leading-display` 1.08 | The marketing display heading |
| `--font-sans`, `--font-mono` | The Geist families |
| Roles in `tokens.ts` | `DISPLAY`, `PAGE_TITLE`, `CARD_TITLE`, `ITEM_TITLE`, `EYEBROW` … import them; don't restate the classes |

### Motion and breakpoints

`--motion-fast` 120ms, `-normal` 150ms, `-slow` 200ms (the `duration-*` utilities);
`--ease-standard`, `-enter`, `-exit`; `--breakpoint-md/lg/xl/wide` (768, 1024, 1280, 1440 px).
`lib/breakpoints.ts` reads the generated values.

The live list, with swatches, is the dev page `/dev/tokens`.

---

## 2b. Palette (C-177)

Dark is a neutral grey with little blue, canvas `#141416` and panel `#1E1E21`; Light keeps `#F5F6FB` and
`#FFFFFF`. There is one solid accent, `brand-strong` `#5550E0`. The hue is indigo, chosen so it can't be
mistaken for Facebook or LinkedIn blue or for the status colours, and the owner kept it on 2026-11-05.
Row marks (the selected bar, the unread dot) use `fg`, and so do chosen tabs, segments and chips, so the
accent is left for main actions, AI moments, links and focus. Measured (WCAG) on the dark values:

| Pair | Ratio |
|---|---|
| `fg` on canvas / panel / overlay / raised-hover | 16.7 / 15.1 / 14.1 / 12.1 |
| `fg-secondary` on canvas / panel / raised / raised-hover | 8.1 / 7.3 / 6.4 / 5.8 (5.8 or more on every surface) |
| `line-control` (composited) on canvas / panel / raised / raised-hover | 4.0 / 3.9 / 3.7 / 3.6 |
| `brand-strong` with `on-brand` | 5.82 |
| `brand-fg` on panel / raised-hover | 8.6 / 6.9 |
| `brand` (marks) on panel / raised / raised-hover | 4.0 / 3.5 / 3.2 |
| `danger-fg` on panel | 8.8 |
| `fg-disabled` on panel | 3.5 (never readable text) |

---

## 3. Exceptions

Some colours are on purpose not "a semantic token in a class": the fixed hues (platform brands,
status, chart series, media scrims), values for places that can't use variables (Clerk, the OG
image, the manifest, emails, static images), and a few marketing effects. They are listed in
`src/styles/colour-exceptions.ts`, each with a reason.

The design lint (`styles/design-lint.test.ts`) reads the list both ways:

- a literal found in code (hex, rgb, hsl, oklch, `color-mix`), an arbitrary colour, shadow or
  gradient value, an inline colour style, or an opacity modifier on a token must be listed, and
- a listed entry that no longer exists fails, so the list can't go stale.

It also fails on: a colour class whose token isn't defined (the `bg-surface` bug), a shadcn alias
class name, a default Tailwind colour, `outline-ring`/`border-ring`/`ring-ring`, a disabled opacity
other than 50, `tracking-[…]`/`leading-[…]`, a bare `rounded`, and `dark:`. Each rule has a
positive and a negative self-test.

To add an exception: first ask whether a token fits. If not, write the entry (`kind: "code"`, the
file under `src/`, the text to allow, and a reason a reviewer can judge), then run
`pnpm exec vitest run src/styles`. Prefer a new named token in globals.css over an exception when
the value will be used more than once; that is how the opacity shades became `panel-glass`,
`media-chip` and the rest.

---

## 4. Changing the look

Values are `light-dark(LIGHT, DARK)` pairs: edit the side you mean. **A new colour token** goes in both
themes: write the pair (or a `color-mix` of another token, or list it in `themeInvariant` with a reason),
add its `use` entry to `colorMeta` in `tokens.ts`, run `pnpm tokens`.

Every recipe is: edit `globals.css`, run `pnpm tokens`, commit the generated files with it, check
`/dev/tokens` and the screens named.

- **Primary colour.** Edit `--color-brand` (marks: focus ring, dots, switch), `--color-brand-strong`
  (fills that carry white text: keep it at 4.5:1 with `on-brand`) and `--color-brand-deep` (the
  logo's bars). Then the tints: `brand-fg` (text on dark), `brand-soft`, `brand-soft-hover` and
  `brand-line` (`rgb(109 106 245 / …)` on dark, `rgb(91 87 234 / …)` on light; change the numbers in both halves), and the glow shadows follow
  by themselves. This changes primary buttons, outgoing bubbles, the focus outline, Clerk's forms,
  charts' main series and the marketing glow. The public site's accent is its own `iris`, so change that
  separately. The logo and icons (`shell-1`, `shell-2`, `node scripts/generate-icons.mjs`) don't follow,
  and stay as they are while business verification uses them.
- **Background and cards.** `--color-canvas` is the page, `--color-panel` cards and the sidebar,
  `--color-field-input` text fields, `--color-raised` selected and focused states, `--color-overlay` what
  floats. Keep the order canvas < field/panel < overlay < raised so the ladder still reads; the veil
  shades follow `panel` and `canvas`.
- **Borders and dividers.** `--color-line` (cards), `--color-line-subtle` (dividers),
  `--color-line-strong` (outline buttons, hovers), `--color-line-control` (control edges; keep 3:1).
- **Text.** `--color-fg`, `--color-fg-secondary` (keep 4.5:1 on every surface), `--color-fg-disabled`.
- **Gradients.** Change the stops in `--gradient-*` (`:root`). The app's fills stay solid; a new gradient
  needs a job that §1.9 of the design system allows, then the variable, a one-line `@utility` and the name
  in `lib/utils.ts` (`bg-token-image`).
- **Shadows.** `--shadow-floating` and `--shadow-overlay` are the app's two elevations, and
  `--shadow-surface` a card's highlight and soft drop; `--shadow-glow*` are the marketing tints (they use `--color-brand`).
- **Radius.** `--radius-lg` and `--radius-xl` move buttons and inputs, and cards and dialogs;
  Clerk follows. Change one step, not the role of a class.
- **Typography and sizing.** Sizes: `--text-2xs`, `--text-md` (and Tailwind's scale). Roles: edit the
  constant in `tokens.ts` (`PAGE_TITLE = "text-2xl …"`); every screen imports it. Eyebrow spacing:
  `--tracking-eyebrow`. Display leading: `--leading-display`. Fonts: `--font-sans` (and the font
  loaded in `app/layout.tsx`).
- **A new colour token.** Add `--color-name` in `@theme`, add its entry (`use`, `swatch`) to
  `colorMeta` in `tokens.ts`, run `pnpm tokens`. The test fails until both exist. Use it as
  `bg-name`, never as a literal.
- **Add a shadcn component.** `pnpm dlx shadcn add …` writes alias names (`bg-popover`); they
  compile, but rewrite them to the tokens before committing (the lint will name each one).

## 5. Solid surfaces

C-177 removed C-128's glass from the app: no `glass-*` utilities, frost tokens, ambient light, grain or
backdrop blur, in menus and dialogs too. Each surface is its token, solid, so nothing depends on what sits
behind it. Cards keep a thin `line-card` edge and a soft drop, which the owner preferred to no edge. The public site's header is its own, intentional exception.

## 6. Checks

`pnpm exec vitest run src/styles` runs the drift test, the token tests and the design lint.
`pnpm lint` and `pnpm exec tsc --noEmit` cover the rest. GitHub CI runs everything.
