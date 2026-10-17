"use client";

import { AlertTriangle, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";

import { UpgradeAction } from "@/components/billing/UpgradeAction";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useTestKnowledge } from "@/lib/api/queries";
import { aiCopy, errorMessage } from "@/lib/copy";

/**
 * FR-KB-03: ask what a customer would and see the drafted answer with the sources it used, or
 * "Not in your knowledge". Nothing is stored or sent (1 AI credit). "Add answer" under a miss opens
 * the FAQ sheet with the question filled in (UI-ISS-069).
 */
export function TestBox({ wid, onAddAnswer }: { wid: string; onAddAnswer?: (question: string) => void }) {
  const test = useTestKnowledge(wid);
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");

  const ask = (event: FormEvent) => {
    event.preventDefault();
    const q = question.trim();
    if (!q || test.isPending) return;
    setAsked(q);
    test.mutate(q);
  };

  const result = test.data;
  return (
    <Card asChild>
      <section aria-labelledby="test-title">
        <CardHeader>
          <CardTitle id="test-title">Test your knowledge</CardTitle>
          <CardDescription>Ask what a customer would. Nothing is sent.</CardDescription>
        </CardHeader>
        <form onSubmit={ask} className="mt-3 flex gap-2">
          <Field id="knowledge-question" className="flex-1">
            <FieldLabel className="sr-only">Question</FieldLabel>
            <Input
              value={question}
              maxLength={1000}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Do you ship to Dubai?"
              autoComplete="off"
            />
          </Field>
          <Button type="submit" variant="secondary" disabled={!question.trim()} loading={test.isPending}>
            Ask
          </Button>
        </form>
        <div aria-live="polite" className="mt-3 empty:hidden">
          {test.isPending ? (
            <div className="space-y-2" aria-busy="true">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </div>
          ) : test.isError ? (
            // Out of credits (402): Upgrade opens the dialog (INLINE_PLAN_LIMITS on the test).
            <Alert tone="danger" icon={<AlertTriangle />} action={<UpgradeAction error={test.error} />}>
              {errorMessage(test.error)}
            </Alert>
          ) : result ? (
            result.can_answer ? (
              <Alert tone="brand" variant="outline" icon={<Sparkles />} data-testid="test-answer">
                <AlertTitle>Answer to “{asked}”</AlertTitle>
                <AlertDescription className="whitespace-pre-wrap text-fg">{result.answer}</AlertDescription>
                {result.sources.length > 0 ? (
                  <ul aria-label="Sources used" className="flex flex-wrap gap-1 pt-1">
                    {result.sources.map((source) => (
                      <li key={source.id} className="max-w-full">
                        <Badge className="max-w-full">
                          <span className="truncate">From: {source.title}</span>
                        </Badge>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </Alert>
            ) : (
              <Alert
                tone="warning"
                variant="outline"
                icon={<AlertTriangle />}
                data-testid="test-answer"
                action={
                  onAddAnswer ? (
                    <AlertAction onClick={() => onAddAnswer(asked)}>Add answer</AlertAction>
                  ) : undefined
                }
              >
                <AlertTitle>{aiCopy.notInKnowledge}</AlertTitle>
                <AlertDescription>
                  {result.missing_info ? `Missing: ${result.missing_info}.` : "Add an FAQ or a note that answers it."}
                </AlertDescription>
              </Alert>
            )
          ) : null}
        </div>
      </section>
    </Card>
  );
}
