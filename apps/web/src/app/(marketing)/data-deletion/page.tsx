import createClient from "openapi-fetch";
import type { paths } from "@socialhood/api-client";
import Link from "next/link";

import type { ReactNode } from "react";

import { Container } from "@/components/marketing/primitives";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { DataDeletionStatus } from "@/lib/api/types";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { pageMetadata } from "@/lib/marketing/seo";
import { cn } from "@/lib/utils";
import { MARKETING_HEADING, READING } from "@/styles/tokens";

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

/** One way to delete data: a card in the list, in the Reading role (15/24), its lead-in in `fg`. */
function Option({ children }: { children: ReactNode }) {
  return (
    <li>
      <Card padding="roomy">
        <p className={cn(READING, "text-fg-secondary")}>{children}</p>
      </Card>
    </li>
  );
}

function HowToDelete({ heading: Heading }: { heading: "h1" | "h2" }) {
  return (
    <section aria-labelledby="how-to-delete" className="mt-2">
      <Heading id="how-to-delete" className={Heading === "h1" ? MARKETING_HEADING : "text-xl font-semibold tracking-tight"}>
        {Heading === "h1" ? "Delete your data" : "How to delete your data"}
      </Heading>
      <ol data-legal-prose="" className="mt-5 space-y-4">
        <Option>
          <strong className="text-fg">Workspace owners</strong>: delete the workspace in Settings → Workspace. Everything
          stops at once, and the workspace&apos;s data, including uploaded media, is permanently removed within 24 hours.
        </Option>
        <Option>
          <strong className="text-fg">Owners and admins, for one account</strong>: in Settings → Connections, use
          Disconnect and delete data (or Remove, for an account already disconnected). The account&apos;s
          conversations, messages, comments, contacts, posts and automations are permanently deleted; the
          workspace&apos;s knowledge, settings and billing stay.
        </Option>
        <Option>
          <strong className="text-fg">Removed Social Hood in Instagram?</strong> If you asked Instagram to delete your
          data, it gives you a confirmation code and a link to this page. Enter the code below to see how your request is
          going.
        </Option>
        <Option>
          <strong className="text-fg">Anyone else</strong>, including people who messaged or commented on a business that
          uses Social Hood: email{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-fg underline underline-offset-4">
            {SUPPORT_EMAIL}
          </a>
          .
        </Option>
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

/**
 * A plain GET form, so it works before (and without) JavaScript. The hint is named on the input
 * in the server HTML too: Field links its descriptions only once it has hydrated.
 */
function CheckStatus({ code }: { code?: string }) {
  return (
    <Card padding="roomy" className="mt-10">
      <form action="/data-deletion" method="get">
        <Field id="code">
          <FieldLabel>Check a request</FieldLabel>
          <FieldDescription id="code-hint">The confirmation code Instagram showed you.</FieldDescription>
          <div className="mt-1.5 flex flex-col gap-2 sm:flex-row">
            <Input
              name="code"
              size="xl"
              defaultValue={code}
              required
              autoComplete="off"
              spellCheck={false}
              aria-describedby="code-hint"
              className="flex-1 font-mono"
            />
            <Button type="submit" size="xl">
              Check status
            </Button>
          </div>
        </Field>
      </form>
    </Card>
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
                <h1 className={MARKETING_HEADING}>{copy.title}</h1>
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
                <h1 className={MARKETING_HEADING}>Request not found</h1>
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
