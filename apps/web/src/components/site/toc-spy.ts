/** The width from which a collapsible contents sits beside the text and stays open (site.css, site-wide 1060). */
export const TOC_WIDE = "(width > 1060px)";

/**
 * Marks the section being read in every `[data-toc]` nav under `root` (C-159): each `a[href="#id"]`
 * there names a section heading by id, and its link gets `aria-current="location"`.
 *
 * One IntersectionObserver watches the headings; its root runs from far above the page down to 35%
 * of the viewport, so a heading "intersects" once it has reached that line, however fast the page
 * jumps (an anchor link, a scrollbar drag). No scroll handler and no layout read. The current section
 * is the last heading that has reached the line; above the first, none is marked.
 *
 * Also:
 * - a collapsible contents (a `details` inside the nav) is kept open on a wide screen;
 * - where the browser has no scroll-driven animations, the reading progress (`--toc-p`, 0 to 1, by
 *   section) is set on `[data-toc-progress]` (the guides' bar; the legal pages' bar is CSS only).
 *
 * Returns a cleanup function.
 */
export function startTocSpy(root: ParentNode = document): () => void {
  const navs = [...root.querySelectorAll<HTMLElement>("[data-toc]")];
  if (!navs.length) return () => {};
  const doc = root instanceof Document ? root : ((root as Node).ownerDocument ?? document);
  const cleanups: (() => void)[] = [];
  const stopAll = () => cleanups.forEach((stop) => stop());

  const disclosures = navs.map((nav) => nav.querySelector("details")).filter((el): el is HTMLDetailsElement => el !== null);
  if (disclosures.length && typeof window.matchMedia === "function") {
    const wide = window.matchMedia(TOC_WIDE);
    const sync = () => {
      if (wide.matches) for (const details of disclosures) details.open = true;
    };
    sync();
    wide.addEventListener("change", sync);
    cleanups.push(() => wide.removeEventListener("change", sync));
  }

  const links = navs.flatMap((nav) => [...nav.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')]);
  const idOf = (link: HTMLAnchorElement) => decodeURIComponent(link.getAttribute("href")!.slice(1));
  const ids = [...new Set(links.map(idOf))].filter(Boolean);
  const targets = ids.map((id) => doc.getElementById(id)).filter((el): el is HTMLElement => el !== null);
  if (!targets.length || typeof IntersectionObserver === "undefined") return stopAll;

  const progress = root.querySelector<HTMLElement>("[data-toc-progress]");
  const native = typeof CSS !== "undefined" && CSS.supports?.("animation-timeline: view()");
  const reached = new Map<Element, boolean>();
  let current: string | undefined;

  const mark = (id: string) => {
    if (id === current) return;
    current = id;
    for (const link of links) {
      if (idOf(link) === id) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
    if (progress && !native) {
      const index = ids.indexOf(id);
      progress.style.setProperty("--toc-p", String(index < 0 ? 0 : (index + 1) / ids.length));
    }
  };

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) reached.set(entry.target, entry.isIntersecting);
      let active = "";
      for (const target of targets) if (reached.get(target)) active = target.id;
      mark(active);
    },
    { rootMargin: "100000px 0px -65% 0px", threshold: 0 },
  );
  for (const target of targets) observer.observe(target);
  cleanups.push(() => observer.disconnect());
  return stopAll;
}
