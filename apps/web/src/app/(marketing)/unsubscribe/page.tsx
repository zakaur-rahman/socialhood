import type { Metadata } from "next";

import { unsubscribeCopy } from "@/lib/copy";

import { UnsubscribeResult } from "./UnsubscribeResult";

export const metadata: Metadata = { title: "Unsubscribe", robots: { index: false, follow: false } };

/** The signed token (C-049, notify/unsubscribe.py): base64url, 66 characters; anything clearly malformed isn't sent. */
const TOKEN = /^[A-Za-z0-9_-]{16,100}$/;

/**
 * FR-NOT-04: the weekly digest's unsubscribe link. Public (proxy.ts protects only /app and /w/):
 * no sign-in, and the page itself posts the token (C-049), so opening the link is the one click.
 */
export default async function UnsubscribePage({ searchParams }: { searchParams: Promise<{ token?: string | string[] }> }) {
  const { token } = await searchParams;
  const value = typeof token === "string" ? token.trim() : "";
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col items-start justify-center gap-3 p-6">
      <div className="bg-shell-gradient mb-3 size-10 rounded-xl" aria-hidden />
      {TOKEN.test(value) ? (
        <UnsubscribeResult token={value} />
      ) : (
        <div role="alert" className="space-y-3">
          <h1 className="text-2xl font-semibold tracking-tight">{unsubscribeCopy.missingTitle}</h1>
          <p className="text-sm text-fg-secondary">{unsubscribeCopy.missing}</p>
        </div>
      )}
    </main>
  );
}
