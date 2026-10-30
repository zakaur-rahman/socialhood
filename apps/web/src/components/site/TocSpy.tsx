"use client";

import { useEffect } from "react";

/** The width from which the contents sit beside the text and stay open (site.css, site-wide 1060). */
export const TOC_WIDE = "(width > 1060px)";

/**
 * Marks the contents link of the section being read (`aria-current="location"`) and keeps the
 * contents open on a wide screen. Works over the server-rendered `[data-toc]` nav: each
 * `a[href="#id"]` there names a heading (or section) by id, and the section that holds it is watched.
 * One IntersectionObserver, no scroll handler and no layout reads per frame. Returns its cleanup.
 */
export function startTocSpy(root: ParentNode = document): () => void {
  const nav = root.querySelector<HTMLElement>("[data-toc]");
  if (!nav) return () => {};

  const cleanups: (() => void)[] = [];
  const details = nav.querySelector("details");
  if (details && typeof window.matchMedia === "function") {
    const wide = window.matchMedia(TOC_WIDE);
    const sync = () => {
      if (wide.matches) details.open = true;
    };
    sync();
    wide.addEventListener("change", sync);
    cleanups.push(() => wide.removeEventListener("change", sync));
  }

  if (typeof IntersectionObserver !== "function") return () => cleanups.forEach((stop) => stop());

  const links = new Map<Element, HTMLAnchorElement>();
  for (const link of nav.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) {
    const id = decodeURIComponent(link.getAttribute("href")!.slice(1));
    const target = id ? document.getElementById(id) : null;
    if (target) links.set(target.closest("section") ?? target, link);
  }
  if (!links.size) return () => cleanups.forEach((stop) => stop());

  const order = [...links.keys()];
  const inBand = new Set<Element>();
  const mark = (current: Element | undefined) => {
    for (const [section, link] of links) {
      if (section === current) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  };
  // The band is a strip across the upper part of the viewport: the section crossing it is the one
  // being read. Sections follow each other, so at most one or two cross it; the first one wins.
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) inBand.add(entry.target);
        else inBand.delete(entry.target);
      }
      const current = order.find((section) => inBand.has(section));
      if (current) mark(current);
    },
    { rootMargin: "-25% 0px -60% 0px" },
  );
  for (const section of order) observer.observe(section);
  cleanups.push(() => observer.disconnect());
  return () => cleanups.forEach((stop) => stop());
}

/** Resolves once the page has loaded and the browser has a moment to spare (as LandingMotion). */
function loaded(): Promise<void> {
  return new Promise((resolve) => {
    const next = () => {
      if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(() => resolve(), { timeout: 800 });
      else setTimeout(resolve, 200);
    };
    if (document.readyState === "complete") next();
    else window.addEventListener("load", next, { once: true });
  });
}

/**
 * C-159: the contents' active item on the long reads (legal pages). Renders nothing; starts after
 * load at an idle moment, so it costs nothing on the first paint. Without it the contents still work
 * as plain links; the reading bar beside it is CSS only (a scroll timeline).
 */
export function TocSpy() {
  useEffect(() => {
    let stop: (() => void) | undefined;
    let cancelled = false;
    void loaded().then(() => {
      if (!cancelled) stop = startTocSpy(document);
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, []);
  return null;
}
