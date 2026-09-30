import type { Route } from "next";
import Link from "next/link";

import { NAV_LINKS } from "@/lib/marketing/site";

import { HeaderAuth } from "./HeaderAuth";
import { MobileMenu } from "./MobileMenu";
import { Logo } from "./primitives";

/** The marketing header: logo, section links, account actions; a menu on phones. */
export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/85 backdrop-blur supports-[backdrop-filter]:bg-canvas/70">
      <div className="relative mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Logo />
        <nav aria-label="Main" className="hidden flex-1 justify-center md:flex">
          <ul className="flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href as Route}
                  className="inline-flex min-h-10 items-center rounded-lg px-3 text-sm text-fg-secondary transition-colors hover:bg-raised hover:text-fg"
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
      </div>
    </header>
  );
}
