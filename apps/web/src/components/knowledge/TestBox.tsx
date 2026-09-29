"use client";

import { AlertTriangle, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useTestKnowledge } from "@/lib/api/queries";
import { aiCopy, errorMessage } from "@/lib/copy";
import { TONE_CLASS } from "@/lib/inbox/format";
import { cn } from "@/lib/utils";

/**
 * FR-KB-03: ask what a customer would and see the drafted answer with the sources it used, or
 * "Not in your knowledge". Nothing is stored or sent (1 AI credit).
 */
export function TestBox({ wid }: { wid: string }) {
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
    <section aria-labelledby="test-title" className="rounded-xl border border-line bg-panel p-4">
      <h2 id="test-title" className="text-base font-semibold">
        Test your knowledge
      </h2>
      <p className="text-xs text-fg-secondary">Ask what a customer would. Nothing is sent.</p>
      <form onSubmit={ask} className="mt-3 flex gap-2">
        <label htmlFor="knowledge-question" className="sr-only">
          Question
        </label>
        <Input
          id="knowledge-question"
          value={question}
          maxLength={1000}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Do you ship to Dubai?"
          autoComplete="off"
        />
        <Button type="submit" className="bg-brand-gradient text-white" disabled={!question.trim() || test.isPending}>
          {test.isPending ? "Asking…" : "Ask"}
        </Button>
      </form>
      <div aria-live="polite" className="mt-3 empty:hidden">
        {test.isPending ? (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-3 w-full bg-raised" />
            <Skeleton className="h-3 w-4/5 bg-raised" />
          </div>
        ) : test.isError ? (
          <p role="alert" className="text-sm text-danger-fg">
            {errorMessage(test.error)}
          </p>
        ) : result ? (
          result.can_answer ? (
            <div className="space-y-2 rounded-lg border border-brand-line bg-field p-3" data-testid="test-answer">
              <p className="flex items-center gap-1.5 text-xs font-medium text-brand-fg">
                <Sparkles className="size-3.5" aria-hidden /> Answer to “{asked}”
              </p>
              <p className="text-sm whitespace-pre-wrap">{result.answer}</p>
              {result.sources.length > 0 ? (
                <ul aria-label="Sources used" className="flex flex-wrap gap-1">
                  {result.sources.map((source) => (
                    <li key={source.id} className={cn("rounded-full px-2 py-0.5 text-[11px]", TONE_CLASS.neutral)}>
                      From: {source.title}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <div className="space-y-1 rounded-lg border border-line bg-field p-3" data-testid="test-answer">
              <p className="flex items-center gap-1.5 text-xs font-medium text-warning">
                <AlertTriangle className="size-3.5" aria-hidden /> {aiCopy.notInKnowledge}
              </p>
              <p className="text-sm text-fg-secondary">
                {result.missing_info ? `Missing: ${result.missing_info}.` : "Add an FAQ or a note that answers it."}
              </p>
            </div>
          )
        ) : null}
      </div>
    </section>
  );
}
