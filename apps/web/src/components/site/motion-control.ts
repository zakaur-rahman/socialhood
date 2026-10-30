/**
 * The pause control's behaviour (C-157, WCAG 2.2.2), plain DOM so the landing page's lazy motion
 * script (landing-motion.ts) can use it without React. Pair it with <MotionToggle /> inside an
 * element marked `data-motion-scope`.
 *
 *   const control = bindMotionControl(scope);
 *   const stop = control.subscribe((paused) => (paused ? stopTimers() : startTimers()));
 *   // in a frame loop: if (control.paused) return;
 *   // on teardown: stop(); control.destroy();
 *
 * - Pausing sets `data-motion-paused` on the scope; site.css then holds every CSS animation inside it
 *   (`animation-play-state: paused`), and scripts read `control.paused` or subscribe.
 * - With `prefers-reduced-motion: reduce` the toggle stays hidden and `paused` is true from the
 *   start: nothing should loop there.
 * - `control.pause()` lets a script stop the motion on its own (off screen, or after 5 s, the other
 *   way to meet 2.2.2); the button shows the paused state so the visitor can resume.
 */
export type MotionControl = {
  /** True while the visitor (or the script) has paused the scope's motion. */
  readonly paused: boolean;
  pause(): void;
  play(): void;
  /** Called with the new state on every change; returns an unsubscribe function. */
  subscribe(listener: (paused: boolean) => void): () => void;
  /** Removes the click handler and hides the toggle again. The paused flag stays as it was. */
  destroy(): void;
};

export const MOTION_SCOPE_ATTR = "data-motion-scope";
export const MOTION_PAUSED_ATTR = "data-motion-paused";
export const MOTION_TOGGLE_SELECTOR = "[data-motion-toggle]";

/** Binds the scope's <MotionToggle /> (its first one); works without a toggle too (scripted pause only). */
export function bindMotionControl(scope: HTMLElement, win: Window = window): MotionControl {
  const toggle = scope.querySelector<HTMLButtonElement>(MOTION_TOGGLE_SELECTOR);
  const reduce = win.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
  const listeners = new Set<(paused: boolean) => void>();
  let paused = scope.hasAttribute(MOTION_PAUSED_ATTR) || reduce;

  const render = () => {
    scope.toggleAttribute(MOTION_PAUSED_ATTR, paused);
    toggle?.setAttribute("aria-pressed", String(paused));
  };
  const set = (next: boolean) => {
    if (next === paused) return;
    paused = next;
    render();
    listeners.forEach((listener) => listener(paused));
  };
  const onClick = () => set(!paused);

  render();
  if (toggle && !reduce) {
    toggle.hidden = false;
    toggle.addEventListener("click", onClick);
  }

  return {
    get paused() {
      return paused;
    },
    pause: () => set(true),
    play: () => {
      if (!reduce) set(false);
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    destroy() {
      listeners.clear();
      if (toggle) {
        toggle.removeEventListener("click", onClick);
        toggle.hidden = true;
      }
    },
  };
}
