import type { Route } from "next";
import Link from "next/link";

import { NAV_LINKS } from "@/lib/marketing/site";
import { tokenValues } from "@/styles/tokens.generated";

import { HeaderAuth } from "./HeaderAuth";
import { HeaderScrollState } from "./HeaderScrollState";
import { MobileMenu } from "./MobileMenu";
import { Logo } from "./primitives";

/**
 * Where the phone header ends: the `site-nav` breakpoint (760 px, globals.css), read here on the
 * server so the menu island gets it as a string and no breakpoint is restated in TypeScript.
 */
const WIDE = `(width > ${tokenValues.breakpoints["site-nav"]})`;

/**
 * The public header (C-155, C-157): the logo, the section links, the account actions, on a sticky
 * paper bar that gains a soft drop once the page scrolls (HeaderScrollState); the links show from
 * the tablet up, and a menu takes them below 760 px. All server-rendered; only the menu's open
 * state, the scrolled flag and the signed-in switch run in the browser. The section links aren't
 * prefetched: they all lead to the home page, which on the home page meant fetching it again (C-152).
 *
 * The two link lists are two landmarks with two names ("Main" in the bar, "Menu" in the phone
 * panel); only one is ever shown.
 */
export function SiteHeader() {
  return (
    <>
      <HeaderScrollState className="nav-sentinel" />
      <header className="nav">
        <div className="wrap nav-in">
          <Logo />
          <nav aria-label="Main">
            <ul className="nav-links">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href as Route} prefetch={false}>
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="nav-r">
            <HeaderAuth />
            <MobileMenu buttonClassName="menu-btn" panelClassName="menu-panel" scrimClassName="menu-scrim" wideQuery={WIDE}>
              <nav aria-label="Menu">
                <ul>
                  {NAV_LINKS.map((link) => (
                    <li key={link.href}>
                      <Link href={link.href as Route} prefetch={false}>
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
                <div className="menu-actions">
                  <HeaderAuth variant="menu" />
                </div>
              </nav>
            </MobileMenu>
          </div>
        </div>
      </header>
    </>
  );
}
