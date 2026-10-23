# Theme: where the values live and how to change them

How the look of the web app is wired, so that one edit reaches every screen, and what to do when
you want to change it. The rules for using the tokens are in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md);
this page is about the machinery and the knobs. Decisions: CONFLICTS C-100.

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
bg-panel, text-fg-secondary, shadow-glow …      tokens.ts (descriptions + type roles) ─► /dev/tokens
                                                colorValue() ─► Clerk, OG image, manifest, viewport,
                                                                 global-error page
                                                generate-icons.mjs reads the .json for the icon colours
```

- **`@theme { … }`** declares the tokens. Tailwind turns `--color-panel` into `bg-panel`,
  `border-panel`, `text-panel` …, `--shadow-glow` into `shadow-glow`, `--radius-xl` into
  `rounded-xl`, `--tracking-eyebrow` into `tracking-eyebrow`. The first line, `--color-*: initial;`,
  switches off Tailwind's default colours (the palette lock, C-075): `bg-red-500` or `bg-surface`
  generates no CSS, and the design lint names it.
- **`:root { … }`** holds what is not a Tailwind theme key: the motion durations (`--motion-*`), the
  gradients as variables (`--gradient-brand` …), and the shadcn aliases.
- **`@utility`** rules make the gradients and a few helpers (`bg-brand-gradient`, `mask-fade-x`,
  `duration-fast`).
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
  they use the variables, `var(--gradient-brand)` and `var(--radius-xl)` included.
- **tailwind-merge** (`lib/utils.ts`) is taught the custom names (`shadow-glow*`, `bg-glow-brand-top`,
  `tracking-eyebrow`, `leading-display`, `duration-*`, `ease-*`) so `cn()` merges them like Tailwind's
  own. A new utility that replaces another of its kind needs a line there.

### Dark only today

The app is dark only: `<html className="dark">` is fixed in `app/layout.tsx`, `:root` sets
`color-scheme: dark`, and there is no light palette, no switch and no `dark:` class in app code
(the lint refuses one). The tokens are shaped so that a light theme is a bounded job, not a rewrite,
but it is not built and not planned. These are the prerequisites if it ever is:

1. A second set of `--color-*` values under a theme selector, for every token in section 2.
2. The state overlays (`hover`, `pressed`, `line*`, `scrim`) are white or black alpha; a light theme
   redefines them as black alpha. Decide the values, there is no mechanical flip.
3. Shadows are black only (`--shadow-floating`, `--shadow-overlay`, the crop mask); light surfaces
   need lighter shadows. The `glow` shadows are brand-tinted and probably fine.
4. `media-scrim` and its steps, and the black photo scrims, must stay dark in any theme.
5. The inverse button (`bg-fg text-canvas`) and `bg-fg` fills flip meaning; check the three places.
6. `statusBarStyle: "black"` and the viewport `themeColor`; the manifest colours.
7. The grain texture over the sidebar and auth panel (`public/grain.jpg`), `mix-blend-lighten` on
   the avatar edge (`ui/avatar.tsx`), and the glows and `canvas`-coloured fades over media.
8. Clerk uses its `dark` base theme; sonner is left on its default theme (`ui/sonner.tsx`).
9. The OG image and the icons are drawn from dark tokens; decide whether they follow a theme.
10. Contrast pairs in DESIGN_SYSTEM §1.11 are all computed on dark surfaces; recheck every pair.

The emails (`apps/api/.../notify/templates/layout.py`) are a separate, light palette on purpose.

---

## 2. The tokens

Where a row says "(shade)", the value is derived from another token with `color-mix`, so changing
the base changes the shade.

### Surfaces

| Token | Controls |
|---|---|
| `canvas` | App and thread background, the page behind everything |
| `panel` | Cards, sidebar, list pane, headers, composer bar, phone drawer |
| `field` | Inputs, incoming bubbles, the segmented track, dialog footers |
| `raised` | Selected row, active segment, focused input, secondary button |
| `raised-hover` | Hover on raised surfaces |
| `overlay` | What floats: popovers, menus, select options, dialogs, sheets, toasts |
| `canvas-veil` (shade) | A dimmed cell or inset: days outside the month, a card in a flow |
| `panel-glass`, `panel-veil` (shades) | Marketing cards over the page glow; the floating marketing nav |

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
| `on-brand` | Text and icons on the brand gradient, `brand-strong`, `danger-fill`, platform fills |
| `on-brand-soft`, `on-brand-line`, `on-brand-line-strong` (shades) | Quiet fill and edges on a brand bubble |

### Lines

| Token | Controls |
|---|---|
| `line` | Card, pane and list edges; the default border colour |
| `line-subtle` | Row dividers inside a card |
| `line-strong` | Outline buttons, hover on cards, the chart axis |
| `line-control` | Edges that identify a control (fields, selects, checkboxes, switches), 3:1 on every surface |

### Brand

| Token | Controls |
|---|---|
| `brand` | Non-text marks: focus outline, dots, selection bar, switch on, chart series |
| `brand-strong` | Solid fills that carry text; the gradient's end; Clerk's primary |
| `brand-deep` | The gradient's start |
| `brand-fg` | Brand-coloured text and icons on dark |
| `brand-soft`, `brand-soft-hover` | Soft brand fills (info tone, soft button) and their hover |
| `brand-line` | Brand borders |
| `shell-1`, `shell-2` | The logo tile and Upgrade button; the icon script reads them |

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

| Variable and utility | Controls |
|---|---|
| `--gradient-brand`, `bg-brand-gradient` | Primary buttons, outgoing bubbles, count badges; Clerk's primary button |
| `--gradient-brand-decor`, `bg-brand-gradient-decor` | Meters, progress fills, decorative icon tiles; never under text |
| `--gradient-shell`, `bg-shell-gradient` | Logo tile and Upgrade only |
| `--gradient-glow-brand`, `bg-glow-brand` | One per view: the plan hero |
| `--gradient-glow-brand-top`, `bg-glow-brand-top` | The glow at the top of a marketing section and illustration card |

### Shadows

| Token | Controls |
|---|---|
| `shadow-floating` | Level 1: popovers, menus, select options, toasts |
| `shadow-overlay` | Level 2: dialogs, alert dialogs, sheets over the scrim |
| `shadow-glow`, `shadow-glow-hover`, `shadow-glow-button` | Marketing: brand-tinted drops under cards, card hover, the primary call to action and the logo mark |
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

Every recipe is: edit `globals.css`, run `pnpm tokens`, commit the generated files with it, check
`/dev/tokens` and the screens named.

- **Primary colour.** Edit `--color-brand` (marks: focus ring, dots, switch), `--color-brand-strong`
  (fills that carry white text: keep it at 4.5:1 with `on-brand`) and `--color-brand-deep` (the
  gradient start). Then the tints: `brand-fg` (text on dark), `brand-soft`, `brand-soft-hover` and
  `brand-line` (they are `rgb(86 127 248 / …)`; change the three numbers), and the glow shadows follow
  by themselves. This changes primary buttons, outgoing bubbles, the focus outline, selected rows'
  bar, Clerk's forms, charts' main series and the marketing glow. The shell colours (`shell-1`,
  `shell-2`) are the logo tile: change them separately, then run `node scripts/generate-icons.mjs`
  to redraw the app icons.
- **Background and cards.** `--color-canvas` is the page, `--color-panel` cards and the sidebar,
  `--color-field` inputs, `--color-raised` selected and focused states, `--color-overlay` what
  floats. Keep the order canvas < field/panel < overlay < raised so the ladder still reads; the glass
  and veil shades follow `panel` and `canvas`.
- **Borders and dividers.** `--color-line` (cards), `--color-line-subtle` (dividers),
  `--color-line-strong` (outline buttons, hovers), `--color-line-control` (control edges; keep 3:1).
- **Text.** `--color-fg`, `--color-fg-secondary` (keep 4.5:1 on every surface), `--color-fg-disabled`.
- **Gradients.** Change the stops in `--gradient-*` (`:root`). A new gradient: add the variable and a
  one-line `@utility`, then the name to `lib/utils.ts` (`bg-token-image`).
- **Shadows.** `--shadow-floating` and `--shadow-overlay` are the app's two elevations;
  `--shadow-glow*` are the marketing tints (they use `--color-brand`).
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

## 5. Checks

`pnpm exec vitest run src/styles` runs the drift test, the token tests and the design lint.
`pnpm lint` and `pnpm exec tsc --noEmit` cover the rest. GitHub CI runs everything.
