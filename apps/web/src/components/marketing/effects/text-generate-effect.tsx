"use client";

import { m, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * Text Generate Effect, from Aceternity UI's free "text-generate-effect"
 * (ui.aceternity.com/components/text-generate-effect), adapted for Social Hood (C-068):
 * - it starts when it scrolls into view, once, instead of on mount;
 * - variants with a stagger instead of useAnimate, so it needs only LazyMotion's features;
 * - with reduced motion the text is simply there;
 * - inherits its colour and size from the caller (tokens), and ends with a blinking caret while
 *   it types.
 */
export function TextGenerateEffect({
  words,
  className,
  stagger = 0.08,
  duration = 0.4,
}: {
  words: string;
  className?: string;
  stagger?: number;
  duration?: number;
}) {
  const ref = useRef<HTMLParagraphElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -15% 0px" });
  const reduce = useReducedMotion();
  const list = words.split(" ");

  if (reduce) {
    return (
      <p ref={ref} className={className}>
        {words}
      </p>
    );
  }
  return (
    <m.p
      ref={ref}
      className={cn(className)}
      initial="hidden"
      animate={inView ? "shown" : "hidden"}
      variants={{ hidden: {}, shown: { transition: { staggerChildren: stagger } } }}
    >
      {list.map((word, index) => (
        <m.span
          key={`${word}-${index}`}
          className="inline"
          variants={{ hidden: { opacity: 0, filter: "blur(6px)" }, shown: { opacity: 1, filter: "blur(0px)" } }}
          transition={{ duration }}
        >
          {word}
          {index < list.length - 1 ? " " : ""}
        </m.span>
      ))}
      <m.span aria-hidden className="ml-0.5 inline-block" variants={{ hidden: { opacity: 0 }, shown: { opacity: 1 } }}>
        <span className="inline-block h-[1em] w-0.5 translate-y-[0.15em] bg-brand motion-safe:animate-[sh-caret_1s_steps(1)_infinite]" />
      </m.span>
    </m.p>
  );
}
