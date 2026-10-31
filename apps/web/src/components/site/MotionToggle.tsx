import { Pause, Play } from "lucide-react";

/**
 * The pause control for looping motion on the public site (C-157, WCAG 2.2.2 "Pause, Stop, Hide").
 * A server component: it renders a round 44 px toggle button, hidden until a script binds it with
 * `bindMotionControl` (motion-control.ts), so a page with no script, or with
 * `prefers-reduced-motion: reduce` (where nothing loops), never shows a control that does nothing.
 *
 * Put it inside the element that holds the looping motion, and mark that element
 * `data-motion-scope`:
 *
 *   <section data-motion-scope="">
 *     <MotionToggle />
 *     …the looping scene…
 *   </section>
 *
 * The name stays the same and `aria-pressed` carries the state (true while paused); the pause and
 * play icons swap in place. Style hook: `.motion-toggle` (site.css); place it with a utility or a
 * class on `className`.
 */
export function MotionToggle({ label = "Pause the animation", className }: { label?: string; className?: string }) {
  return (
    <button
      type="button"
      className={className ? `motion-toggle ${className}` : "motion-toggle"}
      data-motion-toggle=""
      aria-label={label}
      aria-pressed="false"
      hidden
    >
      <span className="mt-icon mt-pause" aria-hidden>
        <Pause className="size-4" strokeWidth={2.2} />
      </span>
      <span className="mt-icon mt-play" aria-hidden>
        <Play className="size-4" strokeWidth={2.2} />
      </span>
    </button>
  );
}
