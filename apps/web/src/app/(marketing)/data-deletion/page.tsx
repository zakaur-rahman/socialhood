import createClient from "openapi-fetch";
import type { paths } from "@socialhood/api-client";
import Link from "next/link";

import { Container } from "@/components/marketing/primitives";
import type { DataDeletionStatus } from "@/lib/api/types";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Data deletion",
  description: "How to delete your data from Social Hood, and the status of a data deletion request made through Instagram.",
  path: "/data-deletion",
});

const STATUS_COPY: Record<DataDeletionStatus["status"], { title: string; body: string }> = {
  received: {
    title: "Request received",
    body: "We have your request and will delete the data we hold for your Instagram account shortly.",
  },
  processing: {
    title: "Deleting your data",
    body: "We have disconnected your Instagram account and are deleting the data we hold for it.",
  },
  completed: {
    title: "Data deleted",
    body: "We have disconnected your Instagram account and deleted the data we held for it: its conversations, messages, comments, contacts, posts and automations.",
  },
  failed: {
    title: "Still deleting your data",
    body: "Part of the deletion didn't finish on the first try. We are retrying it automatically; check back soon.",
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

function HowToDelete({ heading: Heading }: { heading: "h1" | "h2" }) {
  return (
    <section aria-labelledby="how-to-delete" className="mt-2">
      <Heading id="how-to-delete" className={Heading === "h1" ? "text-3xl font-semibold tracking-tight sm:text-4xl" : "text-xl font-semibold tracking-tight"}>
        {Heading === "h1" ? "Delete your data" : "How to delete your data"}
      </Heading>
      <ol className="mt-5 space-y-4 text-[15px] leading-relaxed text-fg-secondary">
        <li className="rounded-xl border border-line bg-panel p-5">
          <strong className="text-fg">Workspace owners</strong>: delete the workspace in Settings → Workspace. Everything
          stops at once, and the workspace&apos;s data, including uploaded media, is permanently removed within 24 hours.
        </li>
        <li className="rounded-xl border border-line bg-panel p-5">
          <strong className="text-fg">Owners and admins, for one account</strong>: in Settings → Connections, use
          Disconnect and delete data (or Remove, for an account already disconnected). The account&apos;s
          conversations, messages, comments, contacts, posts and automations are permanently deleted; the
          workspace&apos;s knowledge, settings and billing stay.
        </li>
        <li className="rounded-xl border border-line bg-panel p-5">
          <strong className="text-fg">Removed Social Hood in Instagram?</strong> If you asked Instagram to delete your
          data, it gives you a confirmation code and a link to this page. Enter the code below to see how your request is
          going.
        </li>
        <li className="rounded-xl border border-line bg-panel p-5">
          <strong className="text-fg">Anyone else</strong>, including people who messaged or commented on a business that
          uses Social Hood: email{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-fg underline underline-offset-4">
            {SUPPORT_EMAIL}
          </a>
          .
        </li>
      </ol>
      <p className="mt-4 text-sm text-fg-secondary">
        What each option deletes, and what we keep, is in our{" "}
        <Link href="/privacy#deleting" className="font-medium text-brand-fg underline underline-offset-4">
          Privacy Policy
        </Link>
        .
      </p>
    </section>
  );
}

function CheckStatus({ code }: { code?: string }) {
  return (
    <form action="/data-deletion" method="get" className="mt-10 rounded-xl border border-line bg-panel p-5">
      <label htmlFor="code" className="text-sm font-semibold">
        Check a request
      </label>
      <p id="code-hint" className="mt-1 text-sm text-fg-secondary">
        The confirmation code Instagram showed you.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          id="code"
          name="code"
          defaultValue={code}
          required
          autoComplete="off"
          spellCheck={false}
          aria-describedby="code-hint"
          className="min-h-11 flex-1 rounded-lg border border-line bg-field px-3 font-mono text-sm text-fg placeholder:text-fg-disabled"
        />
        <button type="submit" className="bg-brand-gradient min-h-11 rounded-lg px-4 text-sm font-medium text-white hover:brightness-110">
          Check status
        </button>
      </div>
    </form>
  );
}

/**
 * F-16: the status URL Meta shows after a data-deletion request, and the public "how to delete
 * your data" page the footer links to. The confirmation code is the only key, and the page shows
 * nothing about the account beyond the request's state.
 */
export default async function DataDeletionPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const { code } = await searchParams;
  const given = typeof code === "string" && code.trim() !== "";
  const valid = given && /^[\w-]{8,64}$/.test(code);
  const request = valid ? await lookup(code) : null;
  const copy = request ? STATUS_COPY[request.status] : null;

  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <Container className="max-w-3xl py-12 sm:py-16">
        {given ? (
          <div className="mb-12 flex flex-col items-start gap-3">
            {copy && request ? (
              <>
                <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{copy.title}</h1>
                <p className="text-sm text-fg-secondary">{copy.body}</p>
                <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                  <dt className="text-fg-secondary">Confirmation code</dt>
                  <dd className="font-mono break-all">{request.confirmation_code}</dd>
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
                <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Request not found</h1>
                <p className="text-sm text-fg-secondary">
                  Check the link from Instagram, or email {SUPPORT_EMAIL} with your confirmation code.
                </p>
              </>
            )}
          </div>
        ) : null}
        <HowToDelete heading={given ? "h2" : "h1"} />
        <CheckStatus code={given ? code : undefined} />
      </Container>
    </main>
  );
}
