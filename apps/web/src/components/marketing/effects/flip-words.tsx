"use client";

import { AnimatePresence, m, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { DURATION, EASE_EXPRESSIVE } from "./motion";

/**
 * Flip Words, from Aceternity UI's free "flip-words" (ui.aceternity.com/components/flip-words),
 * adapted for Social Hood (C-068):
 * - the first word is server-rendered without an entrance, so the headline paints at once (LCP);
 * - every word sits in one grid cell sized to the longest, so changing words never moves the
 *   text around it (no layout shift) and the outgoing word needs no absolute positioning;
 * - it flips only while on screen, and not at all with reduced motion;
 * - aria-hidden: the heading carries the full sentence for screen readers (see Hero);
 * - brand-coloured from the tokens; `m` components for LazyMotion.
 */
export function FlipWords({
  words,
  interval = 2800,
  firstDelay = 4000,
  className,
}: {
  words: string[];
  interval?: number;
  /** The first word stays longer, so the page has finished loading before anything moves. */
  firstDelay?: number;
  className?: string;
}) {
  const [index, setIndex] = useState(0);
  // The first word renders as it is (server-rendered, no entrance); later words animate in.
  const [flipped, setFlipped] = useState(false);
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref);

  useEffect(() => {
    if (reduce || !inView || words.length < 2) return;
    let repeat: number | undefined;
    const next = () => {
      setFlipped(true);
      setIndex((current) => (current + 1) % words.length);
    };
    const first = window.setTimeout(() => {
      next();
      repeat = window.setInterval(next, interval);
    }, flipped ? interval : firstDelay);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(repeat);
    };
  }, [reduce, inView, interval, firstDelay, flipped, words.length]);

  const word = words[index] ?? "";
  return (
    <span ref={ref} aria-hidden data-flip-words className={cn("relative inline-grid text-left align-baseline", className)}>
      {words.map((item) => (
        <span key={item} className="invisible col-start-1 row-start-1 whitespace-nowrap">
          {item}
        </span>
      ))}
      <AnimatePresence initial={false}>
        <m.span
          key={word}
          className="col-start-1 row-start-1 whitespace-nowrap"
          exit={{ opacity: 0, y: "-0.35em", filter: "blur(8px)" }}
          transition={{ duration: DURATION.expressive, ease: EASE_EXPRESSIVE }}
        >
          {word.split("").map((letter, i) => (
            <m.span
              key={`${word}-${i}`}
              className="inline-block"
              initial={flipped ? { opacity: 0, y: "0.3em", filter: "blur(8px)" } : false}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{ duration: DURATION.expressive, ease: EASE_EXPRESSIVE, delay: i * 0.035 }}
            >
              {letter}
            </m.span>
          ))}
        </m.span>
      </AnimatePresence>
    </span>
  );
}
