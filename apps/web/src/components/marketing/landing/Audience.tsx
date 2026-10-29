import type { Route } from "next";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { FOR_BUSINESSES, FOR_CREATORS } from "@/lib/marketing/solutions";

import { SOURCES, type SourceKey } from "./data";

/** The two audience pages, in their own words (lib/marketing/solutions.ts), with the channels each lives on. */
export const AUDIENCES: { page: typeof FOR_CREATORS; channels: SourceKey[] }[] = [
  { page: FOR_CREATORS, channels: ["dm"] },
  { page: FOR_BUSINESSES, channels: ["dm", "whatsapp", "web"] },
];

/**
 * "Who it's for" (C-157, LP-2.8): two links to the audience pages, each with that page's headline and
 * opening line. No new claims, no testimonials. The channel line on top is the page's motif.
 */
export function Audience() {
  return (
    <section className="sec aud-sec" id="who-its-for" aria-labelledby="audience-title">
      <div className="wrap">
        <h2 id="audience-title" className="h2-sm">
          Who it&apos;s for
        </h2>
        <ul className="aud after-head">
          {AUDIENCES.map(({ page, channels }) => (
            <li key={page.path} className="aud-card">
              <span className="chan-line" aria-hidden>
                {channels.map((key) => (
                  <i key={key} style={{ "--c": SOURCES[key].colour } as CSSProperties} />
                ))}
              </span>
              <h3>
                <Link href={page.path as Route} className="aud-link">
                  {page.name}
                  <ArrowRight className="size-5" aria-hidden />
                </Link>
              </h3>
              <p className="aud-h">{page.h1}</p>
              <p className="aud-p">{page.intro}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
