/**
 * The FAQ's height animation where CSS can't do it (C-157 motion; see FaqMotion). A click on a
 * question's summary (a tap, Enter or Space all arrive as one) animates the `<details>` from its
 * height now to its height when open or closed: 250 ms, smooth-out, the accordion's timing in
 * site.css. Opening sets `open` first, so the answer is in the accessibility tree at once; closing
 * marks the item `data-closing` (site.css shows the plus and fades the answer) and drops `open` when
 * the move ends. A second click mid-move reverses it from where it is. Geometry is read on the click
 * only, never per frame.
 */
const DURATION_MS = 250;
const EASE_OUT = "cubic-bezier(0.22, 1, 0.36, 1)";

export function bindFaqMotion(root: ParentNode): () => void {
  const items = [...root.querySelectorAll<HTMLDetailsElement>("details.qa")];
  const running = new Map<HTMLDetailsElement, Animation>();

  const settle = (details: HTMLDetailsElement) => {
    running.delete(details);
    details.style.removeProperty("overflow");
  };

  const onClick = (event: Event) => {
    const summary = event.currentTarget as HTMLElement;
    const details = summary.parentElement as HTMLDetailsElement | null;
    if (!details) return;
    event.preventDefault();
    const closing = details.open && !details.hasAttribute("data-closing");
    // Reads: the height on screen now (mid-move included), then the target.
    const from = details.getBoundingClientRect().height;
    running.get(details)?.cancel();
    let to: number;
    if (closing) {
      to = summary.getBoundingClientRect().height;
      details.setAttribute("data-closing", "");
    } else {
      details.removeAttribute("data-closing");
      details.open = true;
      to = details.getBoundingClientRect().height;
    }
    details.style.overflow = "hidden";
    const animation = details.animate([{ height: `${from}px` }, { height: `${to}px` }], { duration: DURATION_MS, easing: EASE_OUT });
    running.set(details, animation);
    animation.onfinish = () => {
      if (closing) {
        details.open = false;
        details.removeAttribute("data-closing");
      }
      settle(details);
    };
    animation.oncancel = () => {
      if (running.get(details) === animation) settle(details);
    };
  };

  const summaries = items.map((details) => details.querySelector("summary")).filter((s): s is HTMLElement => !!s);
  for (const summary of summaries) summary.addEventListener("click", onClick);
  return () => {
    for (const summary of summaries) summary.removeEventListener("click", onClick);
    running.forEach((animation) => animation.cancel());
  };
}
