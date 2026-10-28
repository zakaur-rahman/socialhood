import type { Route } from "next";
import Link from "next/link";

import { NAV_LINKS } from "@/lib/marketing/site";

import { HeaderAuth } from "./HeaderAuth";
import { MobileMenu } from "./MobileMenu";
import { Logo } from "./primitives";

/** Where the phone header ends (site.css switches at 900 px). */
const WIDE = "(min-width: 901px)";

/**
 * The public header (C-155): the logo, the section links, the account actions, on a sticky paper
 * bar that blurs what scrolls under it; a menu below 900 px. All server-rendered; only the menu's
 * open state and the signed-in switch run in the browser. The section links aren't prefetched:
 * they all lead to the home page, which on the home page meant fetching it again (C-152).
 */
export function SiteHeader() {
  return (
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
          <MobileMenu buttonClassName="menu-btn" panelClassName="menu-panel" wideQuery={WIDE}>
            <nav aria-label="Main">
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
  );
}
