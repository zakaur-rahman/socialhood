import { createCn } from "cn/config";

/**
 * Class merging (shadcn's `cn`: clsx joining plus tailwind-merge's conflict rules), taught the
 * utilities `styles/globals.css` adds, so they merge like Tailwind's own (C-070):
 * - the gradients and the glows are background images in their own group: one replaces another,
 *   an image added after a colour layers over it (`cn("bg-panel", "bg-glow-brand")` keeps both),
 *   and a colour added after one replaces it, so an override like `bg-danger-fill` on a gradient
 *   Button shows the colour, not the gradient on top (`cn("bg-brand-gradient", "bg-danger-fill")`);
 * - the motion tokens are durations and easings (`cn("duration-100", "duration-slow")` keeps one);
 * - the elevation shadows are shadow sizes, not colours (`--color-overlay` exists too), so a call
 *   site's `shadow-xl` replaces a primitive's `shadow-floating` instead of stacking on it (C-071);
 *   so are the crop box's `shadow-crop-mask` (C-073) and the marketing `shadow-glow*` family (C-100);
 * - the glass surfaces (`glass-card` …) are a background colour with a blur: a later `bg-field` or
 *   `glass-pane` replaces one (C-101), and the new shadows (`shadow-glass` …) are shadow sizes too;
 * - `tracking-eyebrow` and `leading-display` are letter spacing and line height, so a later
 *   `tracking-tight` or `leading-tight` replaces them.
 * Everything, the primitives in `components/ui` included, imports `cn` from here; eslint refuses a
 * direct import from "cn".
 */
export const cn = createCn({
  extend: {
    classGroups: {
      "bg-token-image": [{ bg: ["brand-gradient", "brand-gradient-decor", "shell-gradient", "glow-brand", "glow-brand-top"] }],
      duration: [{ duration: ["fast", "normal", "slow"] }],
      ease: [{ ease: ["standard", "enter", "exit"] }],
      shadow: [{ shadow: ["floating", "overlay", "crop-mask", "glow", "glow-hover", "glow-button", "glass", "highlight", "button-primary", "button-secondary"] }],
      glass: [{ glass: ["pane", "card", "float", "raised", "outline"] }],
      tracking: [{ tracking: ["eyebrow"] }],
      leading: [{ leading: ["display"] }],
    },
    conflictingClassGroups: {
      "bg-color": ["bg-token-image", "glass"],
      glass: ["bg-color"],
      "bg-token-image": ["bg-image"],
      "bg-image": ["bg-token-image"],
    },
  },
});
