"use client";

import { useEffect } from "react";

import { captureError } from "@/lib/sentry/client";
import { colorValue, radiusValue } from "@/styles/tokens";

/**
 * The last-resort boundary (RG-07): it replaces the root layout when that layout itself throws, so
 * it carries its own `<html>` and `<body>` and none of the app's styles or components. The look is
 * inline, with the token values from styles/tokens.ts (colorValue), since the CSS isn't loaded.
 */
export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    // C-148: Sentry may not have loaded yet on a public page; this loads it first.
    captureError(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: colorValue("canvas"),
          color: colorValue("fg"),
          fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        }}
      >
        <main role="alert" style={{ maxWidth: 420, padding: "40px 24px", textAlign: "center" }}>
          <h1 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 600 }}>This didn&apos;t load</h1>
          <p style={{ margin: "0 0 20px", fontSize: 14, lineHeight: 1.5, color: colorValue("fg-secondary") }}>
            Something went wrong on our side. Try again. If it keeps happening, email support@amplychat.com.
          </p>
          <button
            type="button"
            onClick={() => retry()}
            style={{
              minHeight: 40,
              padding: "0 16px",
              border: `1px solid ${colorValue("line-strong")}`,
              borderRadius: radiusValue("lg"),
              background: colorValue("panel"),
              color: colorValue("fg"),
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
