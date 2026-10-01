import type { Route } from "next";
import Link from "next/link";

import { NAV_LINKS } from "@/lib/marketing/site";

import { NavBody, Navbar } from "./effects/resizable-navbar";
import { HeaderAuth } from "./HeaderAuth";
import { MobileMenu } from "./MobileMenu";
import { Logo } from "./primitives";

/**
 * The marketing header: logo, section links, account actions; a menu on phones. It floats as a
 * rounded bar once the page scrolls (the resizable navbar, C-068).
 */
export function SiteHeader() {
  return (
    <Navbar>
      <NavBody>
        <Logo />
        <nav aria-label="Main" className="hidden flex-1 justify-center md:flex">
          <ul className="flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href as Route}
                  className="inline-flex min-h-10 items-center rounded-full px-3 text-sm text-fg-secondary transition-colors duration-150 hover:bg-raised hover:text-fg"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <HeaderAuth />
          <MobileMenu />
        </div>
      </NavBody>
    </Navbar>
  );
}
