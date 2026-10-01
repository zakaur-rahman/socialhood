/**
 * Sticky bars never hide the focused control (WCAG 2.4.11; UI-ISS-014, DESIGN_SYSTEM §9).
 *
 * - **Top:** the phone top bar is covered by `scroll-padding-top: 4rem` below md (globals.css).
 * - **Bottom:** a bar stuck to the bottom of the page (the settings save bar, the post composer's
 *   actions) takes `ref={reserveBottomBar}` and `BOTTOM_BAR` in its classes. While it sticks, its
 *   height is the page's bottom scroll padding, so a control the browser scrolls into view (Tab, a
 *   #link, scrollIntoView, Page Down) stops above the bar instead of under it. The bar's own
 *   controls cancel that padding, so tabbing onto them doesn't scroll the page by the bar's height.
 * - **Short viewports** (500 px tall or less: 200% zoom, a landscape phone): bars don't stick, so
 *   they can't take a quarter of the screen (RSP-006); a static bar reserves nothing.
 */

/** A sticky bar stays in the flow on a short viewport. */
export const STATIC_WHEN_SHORT = "[@media(max-height:500px)]:static";

/** A sticky bottom bar's classes, beside `sticky bottom-0`. */
export const BOTTOM_BAR = `${STATIC_WHEN_SHORT} **:-scroll-mb-(--bottom-bar-height)`;

const reserved = new Map<HTMLElement, number>();

/** The tallest sticking bottom bar becomes the root's scroll padding, and the variable its controls cancel. */
function applyReserved() {
  const height = Math.max(0, ...reserved.values());
  const root = document.documentElement.style;
  if (height > 0) {
    root.setProperty("--bottom-bar-height", `${height}px`);
    root.setProperty("scroll-padding-bottom", `${height}px`);
  } else {
    root.removeProperty("--bottom-bar-height");
    root.removeProperty("scroll-padding-bottom");
  }
}

/**
 * The ref for a sticky bottom bar (React 19 ref cleanup). It measures the bar whenever the bar or
 * the viewport changes size, reserves nothing while the bar is static, and gives the space back
 * when the bar unmounts.
 */
export function reserveBottomBar(bar: HTMLElement | null) {
  if (!bar) return;
  const measure = () => {
    reserved.set(bar, getComputedStyle(bar).position === "sticky" ? bar.offsetHeight : 0);
    applyReserved();
  };
  measure();
  const observer = new ResizeObserver(measure);
  observer.observe(bar);
  window.addEventListener("resize", measure);
  return () => {
    observer.disconnect();
    window.removeEventListener("resize", measure);
    reserved.delete(bar);
    applyReserved();
  };
}
