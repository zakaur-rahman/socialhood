"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useTestAutomation } from "@/lib/api/queries";
import type { AutomationTestResult, TriggerName } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";

import { SAMPLE_CONTACT } from "./PreviewPane";

type Kind = "comment" | "dm";

/**
 * UX-SCR-03 Test: type a message or comment and see whether this automation matches, which
 * automation would actually run, and the message it would send. Nothing is sent. The test runs
 * against the saved automation, so pending edits are saved first.
 */
export function MatchTester({
  wid,
  automationId,
  trigger,
  beforeTest,
}: {
  wid: string;
  automationId: string;
  trigger: TriggerName | null | undefined;
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
        <div className="space-y-1.5">
          <Label htmlFor="automation-test-text">{kind === "dm" ? "Message" : "Comment"}</Label>
          <Textarea
            id="automation-test-text"
            value={text}
            maxLength={2000}
            rows={2}
            onChange={(event) => setText(event.target.value)}
            placeholder={kind === "dm" ? "What's the price?" : "LINK please 😍"}
          />
        </div>
        <div className="flex items-center gap-3">
          <Button type="submit" variant="secondary" disabled={!text.trim() || test.isPending}>
            {test.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Test
          </Button>
          <p className="text-xs text-fg-secondary">Nothing is sent.</p>
        </div>
      </form>

      <div aria-live="polite">
        {saveFailed ? (
          <p className="text-sm text-danger-fg">Your latest changes aren&apos;t saved yet. Save them, then test again.</p>
        ) : test.isError ? (
          <p className="text-sm text-danger-fg">{errorMessage(test.error)}</p>
        ) : test.data ? (
          <TestResult result={test.data} automationId={automationId} />
        ) : null}
      </div>
    </div>
  );
}

export function TestResult({ result, automationId }: { result: AutomationTestResult; automationId: string }) {
  const winnerIsThis = result.winner?.id === automationId;
  const winnerText = result.winner
    ? winnerIsThis
      ? "This automation would run."
      : `${result.winner.name} would run instead.`
    : "No automation would run.";
  return (
    <div
      data-result={result.matched ? "match" : "no-match"}
      className={
        result.matched
          ? "space-y-3 rounded-lg border border-success/40 bg-success/10 p-3 text-sm"
          : "space-y-3 rounded-lg border border-line bg-raised p-3 text-sm"
      }
    >
      <p className="flex items-center gap-2 font-semibold">
        {result.matched ? (
          <CheckCircle2 className="size-4 text-success" aria-hidden />
        ) : (
          <XCircle className="size-4 text-fg-secondary" aria-hidden />
        )}
        {result.matched ? "Match" : "No match"}
        {result.matched && result.matched_keyword ? (
          <span className="font-normal text-fg-secondary">on &ldquo;{result.matched_keyword}&rdquo;</span>
        ) : null}
      </p>
      <p>{winnerText}</p>
      {result.reason ? <p className="text-fg-secondary">{result.reason}</p> : null}
      {result.rendered_public_reply ? (
        <div className="space-y-1">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">Public reply</p>
          <p className="rounded-lg bg-field px-3 py-2 break-words whitespace-pre-wrap">{result.rendered_public_reply}</p>
        </div>
      ) : null}
      {result.rendered_message ? (
        <div className="space-y-1">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">DM</p>
          <p className="rounded-lg bg-field px-3 py-2 break-words whitespace-pre-wrap">{result.rendered_message}</p>
        </div>
      ) : null}
    </div>
  );
}
