"use client";

import { useLayoutEffect } from "react";

/**
 * Entrances on scroll, once, for every element with `data-reveal` (effects.css; C-068).
 *
 * The page is server-rendered fully visible. After hydration this marks what is already on screen
 * as shown, then arms the hidden state for the rest and reveals each element the first time it
 * scrolls into view. Without JavaScript, without IntersectionObserver or with reduced motion,
 * nothing is ever hidden. A stagger comes from `--reveal-delay` on the element.
 */
export function ScrollReveal() {
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (!("IntersectionObserver" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const items = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    const height = window.innerHeight;
    for (const item of items) {
      const box = item.getBoundingClientRect();
      if (box.top < height && box.bottom > 0) item.dataset.revealed = "";
    }
    root.dataset.revealArmed = "";

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          (entry.target as HTMLElement).dataset.revealed = "";
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    for (const item of items) if (!("revealed" in item.dataset)) observer.observe(item);
    return () => {
      observer.disconnect();
      delete root.dataset.revealArmed;
    };
  }, []);
  return null;
}
