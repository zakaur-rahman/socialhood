import { ArrowRight, BookOpenText, CircleHelp, LayoutGrid, type LucideIcon, Mail, Newspaper, Workflow } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Ico } from "@/components/marketing/landing/Ico";
import { FEATURES_PATH, HOW_IT_WORKS_PATH, siteHref } from "@/lib/marketing/site";

import { RequestedPath } from "./RequestedPath";

/** Where a lost visitor most likely meant to go: the footer's own labels and addresses. */
const PLACES: { label: string; href: string; icon: LucideIcon }[] = [
  { label: "Features", href: FEATURES_PATH, icon: LayoutGrid },
  { label: "How it works", href: HOW_IT_WORKS_PATH, icon: Workflow },
  { label: "Guides", href: "/guides", icon: BookOpenText },
  { label: "Common questions", href: "/faq", icon: CircleHelp },
  { label: "What's new", href: "/changelog", icon: Newspaper },
  { label: "Contact", href: "/contact", icon: Mail },
];

/**
 * The public site's 404 body (C-159): the head (what happened, the address asked for, the ways
 * out passed in as `children`) beside link cards to the main pages, in the site's card language.
 * Server-rendered; only RequestedPath reads the address in the browser. The app's 404 keeps
 * NotFoundPage.
 */
export function SiteNotFound({ children }: { children: ReactNode }) {
  return (
    <div data-testid="not-found-page" className="nf">
      <div className="wrap">
        <div className="nf-grid">
          <div className="nf-head">
            <p className="kicker">Error 404</p>
            <h1 className="h-page">We can&apos;t find that page</h1>
            <p className="lede">
              The link may be mistyped, or the page may have moved or been deleted. These will get you going again.
            </p>
            <RequestedPath />
            <div className="nf-actions">{children}</div>
          </div>
          <nav aria-label="Popular pages" className="nf-places">
            <ul className="fgrid">
              {PLACES.map((place) => (
                <li key={place.label} className="fcard is-link">
                  <Ico icon={place.icon} />
                  <p className="fcard-t">
                    <Link href={siteHref(place.href) as Route} className="fcard-link">
                      {place.label}
                      <ArrowRight size={16} strokeWidth={1.75} aria-hidden focusable="false" className="fcard-arrow" />
                    </Link>
                  </p>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
    </div>
  );
}
