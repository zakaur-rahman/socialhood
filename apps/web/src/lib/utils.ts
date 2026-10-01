import { createCn } from "cn/config";

/**
 * Class merging (shadcn's `cn`: clsx joining plus tailwind-merge's conflict rules), taught the
 * utilities `styles/globals.css` adds, so a later one replaces an earlier one of its kind just like
 * Tailwind's own (C-070):
 * - the gradients and the glow are background images: they replace each other, not a background
 *   colour (`cn("bg-panel", "bg-glow-brand")` keeps both);
 * - the motion tokens are durations and easings (`cn("duration-100", "duration-slow")` keeps one).
 * Everything, the primitives in `components/ui` included, imports `cn` from here; eslint refuses a
 * direct import from "cn".
 */
export const cn = createCn({
  extend: {
    classGroups: {
      "bg-image": [{ bg: ["brand-gradient", "brand-gradient-decor", "shell-gradient", "glow-brand"] }],
      duration: [{ duration: ["fast", "normal", "slow"] }],
      ease: [{ ease: ["standard", "enter", "exit"] }],
    },
  },
});
