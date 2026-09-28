import type { Metadata } from "next";
import createClient from "openapi-fetch";
import type { paths } from "@socialhood/api-client";

import type { DataDeletionStatus } from "@/lib/api/types";
import { SUPPORT_EMAIL } from "@/lib/copy";

export const metadata: Metadata = { title: "Data deletion status · Social Hood" };

const STATUS_COPY: Record<DataDeletionStatus["status"], { title: string; body: string }> = {
  received: {
    title: "Request received",
    body: "We have your request and will delete the data we hold for your Instagram account shortly.",
  },
  processing: {
    title: "Deleting your data",
    body: "We are deleting the data we hold for your Instagram account.",
  },
  completed: {
    title: "Data deleted",
    body: "We have deleted the data we held for your Instagram account and disconnected it.",
  },
};

async function lookup(code: string): Promise<DataDeletionStatus | null> {
  const api = createClient<paths>({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL });
  try {
    const { data } = await api.GET("/v1/data-deletion/{code}", {
      params: { path: { code } },
      cache: "no-store",
    });
    return data ?? null;
  } catch {
    return null;
  }
}

/**
 * F-16: the status URL Meta shows after a data-deletion request. Public: the confirmation code
 * is the only key, and the page shows nothing about the account beyond the request's state.
 */
export default async function DataDeletionPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const { code } = await searchParams;
  const valid = typeof code === "string" && /^[\w-]{8,64}$/.test(code);
  const request = valid ? await lookup(code) : null;
  const copy = request ? STATUS_COPY[request.status] : null;

  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col items-start justify-center gap-3 p-6">
      <div className="bg-shell-gradient size-10 rounded-xl" aria-hidden />
      {copy && request ? (
        <>
          <h1 className="text-2xl font-semibold tracking-tight">{copy.title}</h1>
          <p className="text-sm text-fg-secondary">{copy.body}</p>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-fg-secondary">Confirmation code</dt>
            <dd className="font-mono">{request.confirmation_code}</dd>
            <dt className="text-fg-secondary">Requested</dt>
            <dd>{new Date(request.created_at).toUTCString()}</dd>
            {request.completed_at ? (
              <>
                <dt className="text-fg-secondary">Completed</dt>
                <dd>{new Date(request.completed_at).toUTCString()}</dd>
              </>
            ) : null}
          </dl>
        </>
      ) : (
        <>
          <h1 className="text-2xl font-semibold tracking-tight">Request not found</h1>
          <p className="text-sm text-fg-secondary">
            Check the link from Instagram, or email {SUPPORT_EMAIL} with your confirmation code.
          </p>
        </>
      )}
    </main>
  );
}
