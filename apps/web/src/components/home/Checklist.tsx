"use client";

import Link from "next/link";
import type { Route } from "next";
import { CheckCircle2, Circle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
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

/** FR-ACC-04 / UX-SCR-01: four steps that tick from data; the first open step is expanded. */
export function Checklist({ steps, slug, onDismiss, dismissing = false }: Props) {
  const done = steps.filter((s) => s.done).length;
  const expanded = steps.find((s) => !s.done)?.key;
  return (
    <section aria-labelledby="checklist-title" className="rounded-xl border border-line bg-panel p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 id="checklist-title" className="text-base font-semibold">
            Get set up
          </h2>
          <p className="text-xs text-fg-secondary tabular-nums">
            {done} of {steps.length} done
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onDismiss} disabled={dismissing} aria-label="Dismiss the checklist">
          <X aria-hidden /> Dismiss
        </Button>
      </div>
      <ol className="space-y-1">
        {steps.map((step) => {
          const copy = COPY[step.key];
          const open = step.key === expanded;
          return (
            <li
              key={step.key}
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
                <p className={cn("text-sm font-medium", step.done && "text-fg-secondary line-through")}>
                  {copy.title}
                </p>
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
        })}
      </ol>
    </section>
  );
}
