"use client";

import { CheckCircle2, ChevronRight, XCircle } from "lucide-react";

import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import type { ChecklistItem } from "@/lib/publishing/types";

/**
 * FR-PUB-10: what must pass before the post can be scheduled, failing items first. Each failing
 * item is a link to the control that fixes it.
 */
export function PostChecklist({
  items,
  failing,
  hrefFor,
  onFix,
}: {
  items: ChecklistItem[];
  failing: number;
  /** The anchor of the control for a field. */
  hrefFor: (field: string | null | undefined) => string;
  onFix: (field: string | null | undefined) => void;
}) {
  return (
    <Card asChild>
     <section aria-labelledby="composer-checklist-title" id="composer-checklist">
      <CardHeader className="mb-2">
        <CardTitle id="composer-checklist-title">Checklist</CardTitle>
        <CardAction>
          <p className="text-xs text-fg-secondary" data-testid="checklist-summary">
            {failing === 0 ? "Ready to schedule" : failing === 1 ? "1 thing to fix" : `${failing} things to fix`}
          </p>
        </CardAction>
      </CardHeader>
      <ul className="space-y-1" aria-label="Checks before scheduling">
        {items.map((item, index) =>
          item.ok ? (
            <li key={`${item.key}-ok`} className="flex items-start gap-2 px-1 py-1 text-sm text-fg-secondary" data-ok="true">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
              <span>
                <span className="sr-only">Passed:</span> {item.message}
              </span>
            </li>
          ) : (
            <li key={`${item.key}-${item.field ?? "none"}-${index}`} data-ok="false">
              <a
                href={hrefFor(item.field)}
                onClick={(event) => {
                  event.preventDefault();
                  onFix(item.field);
                }}
                className="group flex items-start gap-2 rounded-md px-1 py-1.5 text-sm text-fg hover:bg-hover pointer-coarse:min-h-10"
              >
                <XCircle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
                <span className="flex-1">
                  <span className="sr-only">To fix:</span> {item.message}
                </span>
                <span aria-hidden className="flex shrink-0 items-center text-xs text-brand-fg group-hover:underline">
                  Fix <ChevronRight className="size-3.5" aria-hidden />
                </span>
              </a>
            </li>
          ),
        )}
      </ul>
     </section>
    </Card>
  );
}
