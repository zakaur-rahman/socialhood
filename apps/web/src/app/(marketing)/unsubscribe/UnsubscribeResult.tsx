"use client";

import createClient from "openapi-fetch";
import type { paths } from "@socialhood/api-client";
import { CircleCheck, CircleAlert, LoaderCircle, RotateCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { unsubscribeCopy } from "@/lib/copy";
import { PAGE_TITLE } from "@/styles/tokens";

import { NotificationSettingsLink } from "./NotificationSettingsLink";

type Outcome =
  | { kind: "working" }
  | { kind: "done"; workspace: string }
  | { kind: "invalid" }
  | { kind: "failed" };

export type Unsubscriber = (token: string) => Promise<{ status: number; workspace?: string }>;

/** POST /v1/digest/unsubscribe?token= (public, no sign-in; C-049). */
const postUnsubscribe: Unsubscriber = async (token) => {
  const api = createClient<paths>({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL });
  const { data, response } = await api.POST("/v1/digest/unsubscribe", { params: { query: { token } } });
  return { status: response.status, workspace: data?.workspace_name };
};

/**
 * FR-NOT-04 one click: the email's link opens this page, which posts the token once it is open in
 * a browser (a GET never unsubscribes anyone, so link scanners can't). It says what happened.
 */
export function UnsubscribeResult({ token, unsubscribe = postUnsubscribe }: { token: string; unsubscribe?: Unsubscriber }) {
  const [outcome, setOutcome] = useState<Outcome>({ kind: "working" });
  const started = useRef(false);

  const run = useCallback(async () => {
    try {
      const result = await unsubscribe(token);
      if (result.status >= 200 && result.status < 300) setOutcome({ kind: "done", workspace: result.workspace ?? "your workspace" });
      else if (result.status === 404 || result.status === 422) setOutcome({ kind: "invalid" });
      else setOutcome({ kind: "failed" });
    } catch {
      setOutcome({ kind: "failed" });
    }
  }, [token, unsubscribe]);

  useEffect(() => {
    if (started.current) return; // once, also under React's development double effects
    started.current = true;
    void run();
  }, [run]);

  if (outcome.kind === "working") {
    return (
      <div role="status" className="flex items-center gap-3 text-sm text-fg-secondary">
        <LoaderCircle className="size-5 motion-safe:animate-spin" aria-hidden />
        {unsubscribeCopy.working}
      </div>
    );
  }
  if (outcome.kind === "done") {
    return (
      <div role="status" className="space-y-3">
        <CircleCheck className="size-8 text-success" aria-hidden />
        <h1 className={PAGE_TITLE}>{unsubscribeCopy.doneTitle}</h1>
        <p className="text-sm text-fg-secondary">{unsubscribeCopy.done(outcome.workspace)}</p>
        <NotificationSettingsLink />
      </div>
    );
  }
  if (outcome.kind === "invalid") {
    return (
      <div role="alert" className="space-y-3">
        <CircleAlert className="size-8 text-warning" aria-hidden />
        <h1 className={PAGE_TITLE}>{unsubscribeCopy.invalidTitle}</h1>
        <p className="text-sm text-fg-secondary">{unsubscribeCopy.invalid}</p>
        <NotificationSettingsLink />
      </div>
    );
  }
  return (
    <div role="alert" className="space-y-3">
      <CircleAlert className="size-8 text-danger" aria-hidden />
      <h1 className={PAGE_TITLE}>{unsubscribeCopy.failedTitle}</h1>
      <p className="text-sm text-fg-secondary">Something went wrong on our side. Try again.</p>
      <Button
        variant="secondary"
        size="xl"
        onClick={() => {
          setOutcome({ kind: "working" });
          void run();
        }}
      >
        <RotateCw aria-hidden /> Try again
      </Button>
    </div>
  );
}
