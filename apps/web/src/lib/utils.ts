import { createCn } from "cn/config";

/**
 * Class merging (shadcn's `cn`: clsx joining plus tailwind-merge's conflict rules), taught the
 * utilities `styles/globals.css` adds, so they merge like Tailwind's own (C-070):
 * - the gradients and the glow are background images in their own group: one replaces another,
 *   an image added after a colour layers over it (`cn("bg-panel", "bg-glow-brand")` keeps both),
 *   and a colour added after one replaces it, so an override like `bg-danger-fill` on a gradient
 *   Button shows the colour, not the gradient on top (`cn("bg-brand-gradient", "bg-danger-fill")`);
 * - the motion tokens are durations and easings (`cn("duration-100", "duration-slow")` keeps one).
 * Everything, the primitives in `components/ui` included, imports `cn` from here; eslint refuses a
 * direct import from "cn".
 */
export const cn = createCn({
  extend: {
    classGroups: {
      "bg-token-image": [{ bg: ["brand-gradient", "brand-gradient-decor", "shell-gradient", "glow-brand"] }],
      duration: [{ duration: ["fast", "normal", "slow"] }],
      ease: [{ ease: ["standard", "enter", "exit"] }],
    },
    conflictingClassGroups: {
      "bg-color": ["bg-token-image"],
      "bg-token-image": ["bg-image"],
      "bg-image": ["bg-token-image"],
    },
  },
});
