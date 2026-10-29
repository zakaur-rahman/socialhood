"use client";

import { useEffect, useRef } from "react";

/**
 * The header's scrolled state (C-157, LP-3.4): a one-pixel-wide sentinel at the top of the page; once
 * it leaves the viewport the header (the next element) gets `data-scrolled`, and site.css gives it
 * its soft drop. One IntersectionObserver, no scroll listener, nothing read per frame.
 */
export function HeaderScrollState({ className }: { className: string }) {
  const sentinel = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const mark = sentinel.current;
    const header = mark?.nextElementSibling;
    if (!mark || !(header instanceof HTMLElement) || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => {
      header.toggleAttribute("data-scrolled", !entry.isIntersecting);
    });
    observer.observe(mark);
    return () => observer.disconnect();
  }, []);
  return <span ref={sentinel} className={className} aria-hidden />;
}
