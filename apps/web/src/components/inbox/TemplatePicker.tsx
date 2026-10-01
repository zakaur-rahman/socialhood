"use client";

import { useState } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useWhatsAppTemplates } from "@/lib/api/queries";
import type { TemplateSend, WhatsAppTemplate } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** The body with {{1}}…{{n}} replaced by the values typed so far. */
export function fillTemplate(body: string, params: string[]): string {
  return body.replace(/\{\{(\d+)\}\}/g, (match, n: string) => params[Number(n) - 1]?.trim() || match);
}

export type TemplateChoice = TemplateSend & { preview: string };

/**
 * FR-INB-10, UX-INB-07: WhatsApp outside the 24-hour window. Lists approved templates with
 * their language and body; each variable gets an input; the preview shows what the customer
 * will read.
 */
export function TemplatePicker({
  wid,
  accountId,
  open,
  onOpenChange,
  onSend,
}: {
  wid: string;
  accountId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSend: (template: TemplateChoice) => void;
}) {
  const templates = useWhatsAppTemplates(wid, accountId, open);
  const [chosen, setChosen] = useState<WhatsAppTemplate | null>(null);
  const [params, setParams] = useState<string[]>([]);

  const approved = (templates.data ?? []).filter((t) => t.status.toLowerCase() === "approved");
  const ready = chosen && params.length === chosen.param_count && params.every((p) => p.trim());

  const choose = (template: WhatsAppTemplate) => {
    setChosen(template);
    setParams(Array.from({ length: template.param_count }, () => ""));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) setChosen(null);
        onOpenChange(value);
      }}
    >
      <DialogContent className="border-line bg-panel sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Send a template</DialogTitle>
          <DialogDescription className="text-fg-secondary">
            WhatsApp only allows approved templates after the 24-hour window.
          </DialogDescription>
        </DialogHeader>

        {templates.isPending ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading templates">
            <Skeleton className="h-14 w-full bg-raised" />
            <Skeleton className="h-14 w-full bg-raised" />
          </div>
        ) : templates.isError ? (
          <ErrorState error={templates.error} onRetry={() => void templates.refetch()} />
        ) : approved.length === 0 ? (
          <EmptyState
            title="No approved templates"
            body="Create a message template in WhatsApp Manager. Once Meta approves it, it appears here."
          />
        ) : (
          <div className="max-h-[50dvh] space-y-3 overflow-y-auto">
            <ul aria-label="Templates" className="space-y-1.5">
              {approved.map((template) => {
                const selected = chosen?.name === template.name && chosen.language === template.language;
                return (
                  <li key={`${template.name}:${template.language}`}>
                    <button
                      type="button"
                      aria-pressed={selected}
                      onClick={() => choose(template)}
                      className={cn(
                        "w-full rounded-lg border px-3 py-2 text-left",
                        selected ? "border-brand-line bg-brand-soft" : "border-line bg-field hover:bg-raised",
                      )}
                    >
                      <span className="flex items-center justify-between gap-2 text-sm font-medium">
                        {template.name}
                        <span className="text-xs text-fg-secondary">{template.language}</span>
                      </span>
                      <span className="mt-0.5 line-clamp-2 block text-xs text-fg-secondary">{template.body}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {chosen ? (
              <div className="space-y-2 border-t border-line pt-3">
                {params.map((value, i) => (
                  <div key={i} className="space-y-1">
                    <Label htmlFor={`template-param-${i}`} className="text-xs text-fg-secondary">
                      {`Variable {{${i + 1}}}`}
                    </Label>
                    <input
                      id={`template-param-${i}`}
                      value={value}
                      onChange={(event) => setParams(params.map((p, j) => (j === i ? event.target.value : p)))}
                      className="w-full rounded-lg border border-line bg-field px-3 py-2 text-sm focus:bg-raised"
                    />
                  </div>
                ))}
                <p className="text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">Preview</p>
                <p className="rounded-lg bg-field p-3 text-sm whitespace-pre-wrap">{fillTemplate(chosen.body, params)}</p>
              </div>
            ) : null}
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            className="bg-brand-gradient text-white"
            disabled={!ready}
            onClick={() => {
              if (!chosen) return;
              onSend({
                name: chosen.name,
                language: chosen.language,
                params: params.map((p) => p.trim()),
                preview: fillTemplate(chosen.body, params),
              });
              setChosen(null);
              onOpenChange(false);
            }}
          >
            Send template
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
