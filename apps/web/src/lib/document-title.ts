"use client";

import { useEffect } from "react";

/** The suffix `metadata.title.template` adds to every static title (app/layout.tsx). */
const SUFFIX = " · Social Hood";

/**
 * A page whose title depends on data (a contact's name, an automation's name) or that is a client
 * component and can't export `metadata`: sets `document.title` as the layout's template would
 * (WCAG 2.4.2). Next restores the route's metadata title on the next navigation.
 */
export function useDocumentTitle(title: string | null | undefined): void {
  useEffect(() => {
    if (!title) return;
    document.title = `${title}${SUFFIX}`;
  }, [title]);
}
