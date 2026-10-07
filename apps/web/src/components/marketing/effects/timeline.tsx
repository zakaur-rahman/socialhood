"use client";

import { m, useScroll, useSpring } from "framer-motion";
import { useRef, type ReactNode } from "react";

/**
 * Timeline, from Aceternity UI's free "timeline" (ui.aceternity.com/components/timeline), adapted
 * for Social Hood (C-068):
 * - an ordered list with one h3 per step (the original rendered each title twice, for phone and
 *   desktop), and no built-in heading or copy;
 * - the rail fills as the steps scroll past with a transform (scaleY) instead of a measured
 *   height, so nothing is measured and nothing lays out on scroll;
 * - with reduced motion the rail is simply full;
 * - the numbered dots, rail and text use the tokens.
 */
export function Timeline({ items }: { items: { title: string; content: ReactNode }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 70%", "end 60%"] });
  const progress = useSpring(scrollYProgress, { stiffness: 140, damping: 30, restDelta: 0.001 });

  return (
    <div ref={ref} className="relative">
      <div
        aria-hidden
        className="absolute top-5 bottom-5 left-[1.1875rem] w-0.5 overflow-hidden rounded-full bg-line [mask-image:linear-gradient(to_bottom,transparent,black_6%,black_94%,transparent)]"
      >
        <m.div
          style={{ scaleY: progress }}
          className="bg-brand-gradient-decor absolute inset-0 origin-top motion-reduce:transform-none!"
        />
      </div>
      <ol className="relative space-y-14 md:space-y-24">
        {items.map((item, index) => (
          <li key={item.title} className="relative grid gap-5 pl-14 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:gap-10">
            <span
              aria-hidden
              className="bg-brand-gradient absolute top-0 left-0 grid size-10 place-items-center rounded-full text-sm font-semibold text-on-brand tabular-nums ring-4 ring-canvas"
            >
              {index + 1}
            </span>
            <div className="md:sticky md:top-28 md:self-start">
              <h3 className="pt-1.5 text-xl font-semibold tracking-tight text-balance sm:text-2xl">
                <span className="sr-only">Step {index + 1}:</span>{" "}
                {item.title}
              </h3>
            </div>
            <div className="min-w-0">{item.content}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}
