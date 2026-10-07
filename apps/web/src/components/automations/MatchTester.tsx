"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useTestAutomation } from "@/lib/api/queries";
import type { AutomationTestResult, TriggerName } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { EYEBROW } from "@/styles/tokens";

import { SAMPLE_CONTACT } from "./PreviewPane";

type Kind = "comment" | "dm";

/**
 * UX-SCR-03 Test: type a message or comment and see whether this automation matches, which
 * automation would actually run, and the messages it would send: tap first's opening, the message
 * and the follow nudge (FR-AUT-21, 22). Nothing is sent. The test runs against the saved
 * automation, so pending edits are saved first.
 */
export function MatchTester({
  wid,
  automationId,
  trigger,
  openingButton = null,
  beforeTest,
}: {
  wid: string;
  automationId: string;
  trigger: TriggerName | null | undefined;
  /** Tap first's button title (FR-AUT-21), shown with the rendered opening. */
  openingButton?: string | null;
  /** Save pending edits; false when saving failed. */
  beforeTest: () => Promise<boolean>;
}) {
  const [kind, setKind] = useState<Kind>(trigger === "dm_keyword" ? "dm" : "comment");
  const [text, setText] = useState("");
  const [saveFailed, setSaveFailed] = useState(false);
  const test = useTestAutomation(wid, automationId);

  const run = async () => {
    if (!text.trim()) return;
    setSaveFailed(false);
    if (!(await beforeTest())) {
      setSaveFailed(true);
      return;
    }
    test.mutate({ kind, text, first_name: SAMPLE_CONTACT.first_name, username: SAMPLE_CONTACT.username });
  };

  return (
    <div className="space-y-3">
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void run();
        }}
      >
        <ToggleGroup aria-label="Test with" value={kind} onValueChange={(value) => setKind(value as Kind)}>
          <ToggleGroupItem value="comment">A comment</ToggleGroupItem>
          <ToggleGroupItem value="dm">A DM</ToggleGroupItem>
        </ToggleGroup>
        <Field id="automation-test-text">
          <FieldLabel>{kind === "dm" ? "Message" : "Comment"}</FieldLabel>
          <Textarea
            id="automation-test-text"
            value={text}
            maxLength={2000}
            rows={2}
            onChange={(event) => setText(event.target.value)}
            placeholder={kind === "dm" ? "What's the price?" : "LINK please 😍"}
          />
        </Field>
        <div className="flex items-center gap-3">
          <Button type="submit" variant="secondary" disabled={!text.trim() || test.isPending}>
            {test.isPending ? <Spinner /> : null}
            Test
          </Button>
          <p className="text-xs text-fg-secondary">Nothing is sent.</p>
        </div>
      </form>

      <div aria-live="polite">
        {saveFailed ? (
          <Alert tone="danger">Your latest changes aren&apos;t saved yet. Save them, then test again.</Alert>
        ) : test.isError ? (
          <Alert tone="danger">{errorMessage(test.error)}</Alert>
        ) : test.data ? (
          <TestResult result={test.data} automationId={automationId} openingButton={openingButton} />
        ) : null}
      </div>
    </div>
  );
}

export function TestResult({
  result,
  automationId,
  openingButton,
}: {
  result: AutomationTestResult;
  automationId: string;
  /** Tap first's button, shown under the rendered opening (the result carries only its text). */
  openingButton?: string | null;
}) {
  const winnerIsThis = result.winner?.id === automationId;
  const winnerText = result.winner
    ? winnerIsThis
      ? "This automation would run."
      : `${result.winner.name} would run instead.`
    : "No automation would run.";
  return (
    <Alert
      data-result={result.matched ? "match" : "no-match"}
      tone={result.matched ? "success" : "neutral"}
      variant={result.matched ? "soft" : "outline"}
      icon={result.matched ? <CheckCircle2 /> : <XCircle />}
    >
      <div className="space-y-3 text-fg">
      <AlertTitle>
        {result.matched ? "Match" : "No match"}
        {result.matched && result.matched_keyword ? (
          <span className="font-normal text-fg-secondary"> on &ldquo;{result.matched_keyword}&rdquo;</span>
        ) : null}
      </AlertTitle>
      <p>{winnerText}</p>
      {result.reason ? <p className="text-fg-secondary">{result.reason}</p> : null}
      {result.rendered_public_reply ? (
        <div className="space-y-1">
          <p className={EYEBROW}>Public reply</p>
          <p className="rounded-lg bg-field px-3 py-2 break-words whitespace-pre-wrap">{result.rendered_public_reply}</p>
        </div>
      ) : null}
      {result.rendered_opening ? (
        <Rendered label="Opening" testId="test-opening">
          <p className="rounded-lg bg-field px-3 py-2 break-words whitespace-pre-wrap">{result.rendered_opening}</p>
          {openingButton?.trim() ? (
            <Badge tone="brand" size="md">
              {openingButton}
            </Badge>
          ) : null}
        </Rendered>
      ) : null}
      {result.rendered_message ? (
        <Rendered label={result.rendered_opening ? "DM after they tap or reply" : "DM"} testId="test-message">
          <p className="rounded-lg bg-field px-3 py-2 break-words whitespace-pre-wrap">{result.rendered_message}</p>
        </Rendered>
      ) : null}
      {result.rendered_nudge ? (
        <Rendered label="Follow nudge · only if they don't follow you" testId="test-nudge">
          <p className="rounded-lg bg-field px-3 py-2 break-words whitespace-pre-wrap">{result.rendered_nudge}</p>
        </Rendered>
      ) : null}
      </div>
    </Alert>
  );
}

function Rendered({ label, testId, children }: { label: string; testId: string; children: ReactNode }) {
  return (
    <div data-testid={testId} className="space-y-1">
      <p className={EYEBROW}>{label}</p>
      {children}
    </div>
  );
}
