"use client";

import { Menu, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type MouseEvent, type ReactNode } from "react";

/** What Tab can reach inside the panel. */
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * The phone menu (below the site-nav breakpoint, C-155, C-157): a disclosure under the header bar
 * with the section links and Sign in, over a scrim. While it is open:
 * - Tab and Shift+Tab stay inside it (the button and the panel's links), so focus can't wander
 *   behind the scrim;
 * - Escape closes it and returns focus to the button;
 * - a tap or click anywhere outside the button and the panel (the scrim included) closes it;
 * - following a link closes it, and so does growing past the phone layout.
 *
 * The server renders the panel's content and the classes (SiteHeader), so this island holds only the
 * open state: no `cn`, Button, Link or token code reaches the public pages from it (C-152).
 */
export function MobileMenu({
  buttonClassName,
  panelClassName,
  scrimClassName,
  wideQuery,
  children,
}: {
  buttonClassName: string;
  panelClassName: string;
  /** The dimmed layer over the page while the menu is open. */
  scrimClassName?: string;
  /** Where the phone layout ends, from the server (the header's breakpoint). */
  wideQuery: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (returnFocus: boolean) => {
      setOpen(false);
      if (returnFocus) button.current?.focus();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        close(true);
        return;
      }
      if (event.key !== "Tab") return;
      // Focus stays in the menu: the button, then the panel's links and actions, then round again.
      const items = [button.current, ...(panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])].filter(
        (item): item is HTMLElement => item !== null,
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const inside = items.some((item) => item === active);
      if (event.shiftKey && (active === first || !inside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !inside)) {
        event.preventDefault();
        first.focus();
      }
    };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (button.current?.contains(target) || panel.current?.contains(target)) return;
      close(false);
    };
    // Grown past the phone layout, the menu has nothing to show.
    const wide = window.matchMedia(wideQuery);
    const onWide = () => {
      if (wide.matches) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointerDown);
    wide.addEventListener("change", onWide);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointerDown);
      wide.removeEventListener("change", onWide);
    };
  }, [open, wideQuery]);

  // Following any link in the panel closes it.
  const onPanelClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target instanceof Element && event.target.closest("a")) setOpen(false);
  };

  return (
    <div>
      <button
        ref={button}
        type="button"
        className={buttonClassName}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
      </button>
      {scrimClassName ? <div className={scrimClassName} hidden={!open} aria-hidden /> : null}
      <div ref={panel} id={panelId} hidden={!open} className={panelClassName} onClick={onPanelClick}>
        {children}
      </div>
    </div>
  );
}
