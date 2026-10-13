"use client";

import Link from "next/link";
import type { Route } from "next";
import { useState } from "react";
import { CheckCircle2, ChevronDown, Circle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ChecklistStep } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type StepCopy = { title: string; why: string; action: string; href: (slug: string) => Route };

// Pages that later phases build are cast until they exist (see components/shell/nav.ts).
const COPY: Record<ChecklistStep["key"], StepCopy> = {
  connect_account: {
    title: "Connect an account",
    why: "Bring your Instagram and WhatsApp messages into one inbox.",
    action: "Connect an account",
    href: (s) => `/w/${s}/settings/connections` as Route,
  },
  add_knowledge: {
    title: "Add knowledge",
    why: "Teach the AI your prices, shipping and FAQs so its replies are right.",
    action: "Add knowledge",
    href: (s) => `/w/${s}/knowledge` as Route,
  },
  choose_ai_mode: {
    title: "Choose an AI mode",
    why: "Decide whether the AI suggests replies or answers on its own.",
    action: "Choose a mode",
    // Each account's mode is set on its card in Connections (AiModeControl); done once an
    // account's mode is Suggest or Auto (C-060).
    href: (s) => `/w/${s}/settings/connections` as Route,
  },
  create_automation: {
    title: "Create an automation",
    why: "Send a DM automatically when someone comments a keyword.",
    action: "Browse templates",
    // F-11: straight to the template gallery.
    href: (s) => `/w/${s}/automations/new` as Route,
  },
};

type Props = {
  steps: ChecklistStep[];
  slug: string;
  onDismiss: () => void;
  dismissing?: boolean;
};

function StepRow({ step, slug, open }: { step: ChecklistStep; slug: string; open: boolean }) {
  const copy = COPY[step.key];
  return (
    <li
      data-step={step.key}
      data-done={step.done}
      className={cn("flex gap-3 rounded-lg px-2 py-2", open && "bg-hover")}
    >
      {step.done ? (
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-label="Done" />
      ) : (
        <Circle className="mt-0.5 size-5 shrink-0 text-fg-disabled" aria-label="Not done" />
      )}
      <div className="min-w-0 flex-1">
        <p className={cn("text-sm font-medium", step.done && "text-fg-secondary line-through")}>{copy.title}</p>
        {open ? (
          <>
            <p className="mt-0.5 text-sm text-fg-secondary">{copy.why}</p>
            <Button asChild size="sm" className="mt-2">
              <Link href={copy.href(slug)}>{copy.action}</Link>
            </Button>
          </>
        ) : null}
      </div>
    </li>
  );
}

/**
 * FR-ACC-04 / UX-SCR-01: four steps that tick from data; the first open step is expanded. Done
 * steps fold into one "N done" row while others are open (UI-058). When every step is done it is a
 * one-line "You're all set" (Home shows it for one session, then hides the card).
 */
export function Checklist({ steps, slug, onDismiss, dismissing = false }: Props) {
  const [showDone, setShowDone] = useState(false);
  const done = steps.filter((s) => s.done);
  const open = steps.filter((s) => !s.done);
  const expanded = open[0]?.key;

  const dismiss = (
    <Button variant="ghost" size="sm" onClick={onDismiss} loading={dismissing} aria-label="Dismiss the checklist">
      <X aria-hidden /> Dismiss
    </Button>
  );

  if (open.length === 0) {
    return (
      <Card asChild>
        <section aria-labelledby="checklist-title" data-state="all-set">
          <CardHeader>
            <CardTitle id="checklist-title" className="flex items-center gap-2">
              <CheckCircle2 className="size-5 shrink-0 text-success" aria-hidden /> You&apos;re all set
            </CardTitle>
            <CardDescription>All {steps.length} setup steps are done.</CardDescription>
            <CardAction>{dismiss}</CardAction>
          </CardHeader>
        </section>
      </Card>
    );
  }

  return (
    <Card asChild className="space-y-3">
      <section aria-labelledby="checklist-title">
        <CardHeader>
          <CardTitle id="checklist-title">Get set up</CardTitle>
          <CardDescription className="tabular-nums">
            {done.length} of {steps.length} done
          </CardDescription>
          <CardAction>{dismiss}</CardAction>
        </CardHeader>
        {done.length > 0 ? (
          <div>
            <Button
              variant="ghost"
              size="sm"
              aria-expanded={showDone}
              aria-controls="checklist-done"
              onClick={() => setShowDone((value) => !value)}
            >
              <ChevronDown className={cn("transition-transform", showDone && "rotate-180")} aria-hidden />
              {done.length === 1 ? "1 step done" : `${done.length} steps done`}
            </Button>
            <ol id="checklist-done" hidden={!showDone} className="space-y-1">
              {done.map((step) => (
                <StepRow key={step.key} step={step} slug={slug} open={false} />
              ))}
            </ol>
          </div>
        ) : null}
        <ol className="space-y-1">
          {open.map((step) => (
            <StepRow key={step.key} step={step} slug={slug} open={step.key === expanded} />
          ))}
        </ol>
      </section>
    </Card>
  );
}
