"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

const SHOWN_MS = 2000;

/** A code block in the developer pages (the `.cx-code` style), focusable so a keyboard can scroll it, with a copy button. */
export function Code({ children }: { children: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (state === "idle") return;
    const timer = window.setTimeout(() => setState("idle"), SHOWN_MS);
    return () => window.clearTimeout(timer);
  }, [state]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(children);
      setState("copied");
    } catch {
      setState("failed"); // no clipboard access: the text stays selectable by hand
    }
  }

  return (
    <>
    <div className="cx-code-wrap">
      <pre className="cx-code" tabIndex={0}>
        <code>{children}</code>
      </pre>
      <button type="button" className="cx-copy" aria-label="Copy" onClick={() => void copy()}>
        {state === "copied" ? <Check aria-hidden /> : <Copy aria-hidden />}
      </button>
    </div>
      {/* A failed copy is written out: the icon alone would look as if the click did nothing. */}
      <p role="status" className={state === "failed" ? "cx-note" : "sr-only"}>
        {state === "copied" ? "Copied" : state === "failed" ? "Couldn't copy. Select the text and copy it by hand." : ""}
      </p>
    </>
  );
}
