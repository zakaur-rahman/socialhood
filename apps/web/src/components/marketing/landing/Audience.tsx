import type { Route } from "next";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { FOR_BUSINESSES, FOR_CREATORS } from "@/lib/marketing/solutions";

/** The two audience pages, in their own words (lib/marketing/solutions.ts). */
export const AUDIENCES = [FOR_CREATORS, FOR_BUSINESSES];

/**
 * "Who it's for" (C-157, LP-2.8): two links to the audience pages, each with that page's headline and
 * opening line. No new claims, no testimonials, and no icon tile or channel stripe (the design audit, 2026-11-06).
 */
export function Audience() {
  return (
    <section className="sec aud-sec" id="who-its-for" aria-labelledby="audience-title">
      <div className="wrap">
        <h2 id="audience-title" className="h2-sm">
          Who it&apos;s for
        </h2>
        <ul className="aud after-head">
          {AUDIENCES.map((page) => (
            <li key={page.path} className="aud-card">
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
