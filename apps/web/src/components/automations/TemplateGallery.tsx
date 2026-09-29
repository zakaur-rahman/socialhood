"use client";

import { ArrowLeft, Loader2, Plus, Sparkles } from "lucide-react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateAutomation } from "@/lib/api/queries";
import type { AutomationTemplate, SocialAccount, TemplateCategory } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { DEFAULT_NAME } from "@/lib/automations/definition";
import { CATEGORY_LABEL, TRIGGER_LABEL } from "@/lib/automations/format";
import { errorMessage } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { TemplateIcon } from "./TemplateIcon";

const CATEGORIES: (TemplateCategory | "all")[] = ["all", "grow", "sell", "support"];
const ACTION_TAG = { send_message: "Message", ai_reply: "AI reply" } as const;

/** What the user picked: a template, or null for Start from blank. */
export type Choice = AutomationTemplate | null;

/** The editor URL that opens with the first incomplete step focused (UX-SCR-11). */
export function editorHref(slug: string, id: string, focusFirst = false): Route {
  return `/w/${slug}/automations/${id}${focusFirst ? "?focus=first" : ""}` as Route;
}

/**
 * F-11: create the draft (from a template or blank) and open the editor on it. The caller asks
 * for the account first when the workspace has more than one Instagram account.
 */
export function useStartAutomation() {
  const workspace = useCurrentWorkspace();
  const router = useRouter();
  const create = useCreateAutomation(workspace.id);
  const start = (choice: Choice, accountId: string | null) =>
    create.mutate(
      choice
        ? { template_key: choice.key, social_account_id: accountId }
        : { name: DEFAULT_NAME, social_account_id: accountId },
      {
        onSuccess: (automation) => router.push(editorHref(workspace.slug, automation.id, true)),
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  return { start, pending: create.isPending, pendingKey: create.isPending ? (create.variables?.template_key ?? "blank") : null };
}

/**
 * UX-SCR-11: the template gallery. Category chips, a card per template, Start from blank last.
 * With several Instagram accounts it asks which one before creating the draft.
 */
export function TemplateGallery({
  open,
  onOpenChange,
  templates,
  templatesLoading,
  accounts,
  initialChoice,
  plan,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  templates: AutomationTemplate[];
  templatesLoading: boolean;
  /** Connected Instagram accounts. */
  accounts: SocialAccount[];
  /** Opened from an empty-state card: go straight to the account question. */
  initialChoice?: Choice;
  plan: "free" | "pro" | "max";
}) {
  const [category, setCategory] = useState<TemplateCategory | "all">("all");
  const [asking, setAsking] = useState<{ choice: Choice } | null>(
    initialChoice !== undefined ? { choice: initialChoice } : null,
  );
  const [accountId, setAccountId] = useState<string | null>(accounts[0]?.id ?? null);
  const { start, pending, pendingKey } = useStartAutomation();

  const choose = (choice: Choice) => {
    if (accounts.length > 1) {
      setAsking({ choice });
      return;
    }
    start(choice, accounts[0]?.id ?? null);
  };

  const shown = templates.filter((template) => category === "all" || template.category === category);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setAsking(null);
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto border-line bg-panel sm:max-w-3xl">
        {asking ? (
          <AccountQuestion
            choice={asking.choice}
            accounts={accounts}
            accountId={accountId}
            onAccountChange={setAccountId}
            onBack={() => setAsking(null)}
            onContinue={() => start(asking.choice, accountId)}
            pending={pending}
          />
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="text-xl font-semibold">New automation</DialogTitle>
              <DialogDescription className="text-fg-secondary">
                Start from a template and change anything, or start from blank.
              </DialogDescription>
            </DialogHeader>
            <div role="group" aria-label="Categories" className="flex flex-wrap gap-1.5">
              {CATEGORIES.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={category === value}
                  onClick={() => setCategory(value)}
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium",
                    category === value ? "bg-brand-soft text-brand-fg" : "text-fg-secondary hover:bg-white/5 hover:text-fg",
                  )}
                >
                  {value === "all" ? "All" : CATEGORY_LABEL[value]}
                </button>
              ))}
            </div>
            <ul aria-label="Templates" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {templatesLoading
                ? Array.from({ length: 5 }, (_, i) => (
                    <li key={i} aria-hidden>
                      <Skeleton className="h-44 rounded-xl bg-raised" />
                    </li>
                  ))
                : shown.map((template) => (
                    <li key={template.key}>
                      <TemplateCard
                        template={template}
                        showPro={template.requires_paid_plan && plan === "free"}
                        pending={pendingKey === template.key}
                        disabled={pending}
                        onUse={() => choose(template)}
                      />
                    </li>
                  ))}
              <li>
                <div className="flex h-full min-h-44 flex-col rounded-xl border border-dashed border-line-strong p-4">
                  <span className="grid size-9 place-items-center rounded-lg bg-raised text-fg-secondary">
                    <Plus className="size-5" aria-hidden />
                  </span>
                  <p className="mt-3 text-sm font-semibold">Start from blank</p>
                  <p className="mt-1 flex-1 text-sm text-fg-secondary">Choose the trigger, keywords and reply yourself.</p>
                  <Button
                    variant="secondary"
                    className="mt-3 self-start"
                    disabled={pending}
                    onClick={() => choose(null)}
                  >
                    {pendingKey === "blank" ? <Loader2 className="animate-spin" aria-hidden /> : null}
                    Start from blank
                  </Button>
                </div>
              </li>
            </ul>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function TemplateCard({
  template,
  showPro,
  pending,
  disabled,
  onUse,
}: {
  template: AutomationTemplate;
  showPro: boolean;
  pending: boolean;
  disabled: boolean;
  onUse: () => void;
}) {
  const titleId = `template-${template.key}`;
  return (
    <article aria-labelledby={titleId} className="flex h-full min-h-44 flex-col rounded-xl border border-line bg-field p-4">
      <div className="flex items-start justify-between gap-2">
        <span className="bg-brand-gradient-decor grid size-9 place-items-center rounded-lg text-white">
          <TemplateIcon name={template.icon} className="size-5" />
        </span>
        {showPro ? <ProBadge /> : null}
      </div>
      <h3 id={titleId} className="mt-3 text-sm font-semibold">
        {template.name}
      </h3>
      <p className="mt-1 flex-1 text-sm text-fg-secondary">{template.outcome}</p>
      <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
        <span className="rounded-full bg-raised px-2 py-0.5 text-fg-secondary">{TRIGGER_LABEL[template.trigger]}</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-raised px-2 py-0.5 text-fg-secondary">
          {template.action === "ai_reply" ? <Sparkles className="size-3" aria-hidden /> : null}
          {ACTION_TAG[template.action]}
        </span>
      </div>
      <Button
        className="bg-brand-gradient mt-3 self-start text-white"
        disabled={disabled}
        onClick={onUse}
        aria-label={`Use template: ${template.name}`}
      >
        {pending ? <Loader2 className="animate-spin" aria-hidden /> : null}
        Use template
      </Button>
    </article>
  );
}

export function ProBadge() {
  return (
    <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-semibold text-brand-fg">Pro</span>
  );
}

function AccountQuestion({
  choice,
  accounts,
  accountId,
  onAccountChange,
  onBack,
  onContinue,
  pending,
}: {
  choice: Choice;
  accounts: SocialAccount[];
  accountId: string | null;
  onAccountChange: (id: string) => void;
  onBack: () => void;
  onContinue: () => void;
  pending: boolean;
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onContinue();
      }}
      className="space-y-4"
    >
      <DialogHeader>
        <DialogTitle className="text-xl font-semibold">Which account?</DialogTitle>
        <DialogDescription className="text-fg-secondary">
          {choice ? `${choice.name} will answer on this Instagram account.` : "The automation answers on this Instagram account."}
        </DialogDescription>
      </DialogHeader>
      <fieldset className="space-y-2">
        <legend className="sr-only">Instagram account</legend>
        {accounts.map((account) => (
          <label
            key={account.id}
            className={cn(
              "flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm",
              accountId === account.id ? "border-brand bg-brand-soft" : "border-line hover:bg-white/5",
            )}
          >
            <input
              type="radio"
              name="automation-account"
              value={account.id}
              checked={accountId === account.id}
              onChange={() => onAccountChange(account.id)}
              className="accent-brand"
            />
            <span className="font-medium">{accountLabel(account)}</span>
            {account.display_name && account.username ? (
              <span className="truncate text-fg-secondary">{account.display_name}</span>
            ) : null}
          </label>
        ))}
      </fieldset>
      <div className="flex justify-between gap-2">
        <Button type="button" variant="ghost" onClick={onBack}>
          <ArrowLeft aria-hidden /> Back
        </Button>
        <Button type="submit" className="bg-brand-gradient text-white" disabled={!accountId || pending}>
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          {choice ? "Use template" : "Start from blank"}
        </Button>
      </div>
    </form>
  );
}
