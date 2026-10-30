/**
 * Marks the section being read in every `[data-toc]` on the page (C-159). One IntersectionObserver
 * watches the sections' headings; its root runs from far above the page down to 35% of the viewport,
 * so a heading "intersects" once it has reached that line, however fast the page jumps (an anchor
 * link, a scrollbar drag). No scroll handler and no layout read. The current section is the last
 * heading that has reached the line. Where the browser has no scroll-driven animations, it also sets the reading
 * progress (`--toc-p`, 0 to 1, by section) on `[data-toc-progress]`.
 *
 * Returns a cleanup function.
 */
export function startTocSpy(doc: Document = document): () => void {
  const links = [...doc.querySelectorAll<HTMLAnchorElement>("[data-toc] a[data-toc-link]")];
  const ids = [...new Set(links.map((link) => link.dataset.tocLink ?? ""))].filter(Boolean);
  const targets = ids.map((id) => doc.getElementById(id)).filter((el): el is HTMLElement => el !== null);
  if (!targets.length || typeof IntersectionObserver === "undefined") return () => {};

  const progress = doc.querySelector<HTMLElement>("[data-toc-progress]");
  const native = typeof CSS !== "undefined" && CSS.supports?.("animation-timeline: view()");
  const reached = new Map<Element, boolean>();
  let current = "";

  const mark = (id: string) => {
    if (id === current) return;
    current = id;
    for (const link of links) {
      if (link.dataset.tocLink === id) link.setAttribute("aria-current", "location");
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
  return () => observer.disconnect();
}
