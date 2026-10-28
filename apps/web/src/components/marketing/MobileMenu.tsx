"use client";

import { Menu, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type MouseEvent, type ReactNode } from "react";

/**
 * The phone menu (below md): a disclosure under the header bar with the section links and the
 * account actions. Escape or following a link closes it; Escape returns focus to the button.
 *
 * The server renders the panel's content and the button's classes (SiteHeader), so this island
 * holds only the open state: no `cn`, Button, Link or token code reaches the public pages from it
 * (C-152).
 */
export function MobileMenu({
  buttonClassName,
  panelClassName,
  wideQuery,
  children,
}: {
  buttonClassName: string;
  panelClassName: string;
  /** Where the phone layout ends (`minWidth("md")`), from the server so the token mirror stays there. */
  wideQuery: string;
  children: ReactNode;
}) {
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
    const wide = window.matchMedia(wideQuery);
    const onWide = () => {
      if (wide.matches) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    wide.addEventListener("change", onWide);
    return () => {
      document.removeEventListener("keydown", onKey);
      wide.removeEventListener("change", onWide);
    };
  }, [open, wideQuery]);

  // Following any link in the panel closes it.
  const onPanelClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target instanceof Element && event.target.closest("a")) setOpen(false);
  };

  return (
    <div className="md:hidden">
      <button
        ref={button}
        type="button"
        data-slot="button"
        data-variant="ghost"
        data-size="icon-lg"
        className={buttonClassName}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
      </button>
      <div id={panelId} hidden={!open} className={panelClassName} onClick={onPanelClick}>
        {children}
      </div>
    </div>
  );
}
