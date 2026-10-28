import type { Route } from "next";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { minWidth } from "@/lib/breakpoints";
import { NAV_LINKS } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { NavBody, Navbar } from "./effects/resizable-navbar";
import { HeaderAuth } from "./HeaderAuth";
import { MobileMenu } from "./MobileMenu";
import { Logo, MARKETING_CARD } from "./primitives";

/**
 * The marketing header: logo, section links, account actions; a menu on phones. It floats as a
 * rounded bar once the page scrolls (the resizable navbar, C-068). The section links aren't
 * prefetched: they all lead to the home page, which on the home page meant fetching it again (C-152).
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
                  prefetch={false}
                  className="inline-flex min-h-10 items-center rounded-full px-3 text-sm text-fg-secondary transition-colors duration-normal hover:bg-hover hover:text-fg"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <HeaderAuth />
          {/* It floats over the page, so the floating elevation (DESIGN_SYSTEM §6), on the panel. */}
          <MobileMenu
            buttonClassName={buttonVariants({ variant: "ghost", size: "icon-lg" })}
            panelClassName={cn(MARKETING_CARD, "absolute inset-x-0 top-full mt-2 shadow-floating")}
            wideQuery={minWidth("md")}
          >
            <nav aria-label="Main" className="px-3 pt-2 pb-4">
              <ul className="grid">
                {NAV_LINKS.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href as Route}
                      prefetch={false}
                      className="flex min-h-11 items-center rounded-lg px-2 text-base text-fg transition-colors duration-normal hover:bg-hover"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
              <div className="mt-3 border-t border-line pt-4">
                <HeaderAuth variant="menu" />
              </div>
            </nav>
          </MobileMenu>
        </div>
      </NavBody>
    </Navbar>
  );
}
