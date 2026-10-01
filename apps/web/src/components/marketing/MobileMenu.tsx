"use client";

import { Menu, X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { NAV_LINKS } from "@/lib/marketing/site";

import { HeaderAuth } from "./HeaderAuth";

/**
 * The phone menu (below md): a disclosure under the header bar with the section links and the
 * account actions. Escape or following a link closes it; Escape returns focus to the button.
 */
export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    // Grown past the phone layout, the menu has nothing to show.
    const wide = window.matchMedia("(min-width: 48rem)");
    const onWide = () => {
      if (wide.matches) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    wide.addEventListener("change", onWide);
    return () => {
      document.removeEventListener("keydown", onKey);
      wide.removeEventListener("change", onWide);
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <div className="md:hidden">
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((value) => !value)}
        className="grid size-11 place-items-center rounded-lg text-fg transition-colors duration-150 hover:bg-raised"
      >
        {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
      </button>
      <div
        id={panelId}
        hidden={!open}
        className="absolute inset-x-0 top-full mt-2 rounded-2xl border border-line bg-panel shadow-2xl shadow-black/60"
      >
        <nav aria-label="Main" className="px-3 pt-2 pb-4">
          <ul className="grid">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href as Route}
                  onClick={close}
                  className="flex min-h-11 items-center rounded-lg px-2 text-base text-fg hover:bg-raised"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-3 border-t border-line pt-4">
            <HeaderAuth variant="menu" onNavigate={close} />
          </div>
        </nav>
      </div>
    </div>
  );
}
