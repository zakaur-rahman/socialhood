"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

/**
 * The last-resort boundary (RG-07): it replaces the root layout when that layout itself throws, so
 * it carries its own `<html>` and `<body>` and none of the app's styles or components. The look is
 * inline and follows the dark canvas and brand tokens (styles/tokens.ts) by value.
 */
export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    Sentry.captureException(error);
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
          background: "#000000",
          color: "#f5f5f5",
          fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        }}
      >
        <main role="alert" style={{ maxWidth: 420, padding: "40px 24px", textAlign: "center" }}>
          <h1 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 600 }}>This didn&apos;t load</h1>
          <p style={{ margin: "0 0 20px", fontSize: 14, lineHeight: 1.5, color: "#b3b3b3" }}>
            Something went wrong on our side. Try again. If it keeps happening, email support@socialhood.com.
          </p>
          <button
            type="button"
            onClick={() => retry()}
            style={{
              minHeight: 40,
              padding: "0 16px",
              border: "1px solid #3a3a3a",
              borderRadius: 8,
              background: "#1f1f1f",
              color: "#f5f5f5",
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
