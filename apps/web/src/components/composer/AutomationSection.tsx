"use client";

import { ArrowLeft, MessageSquareReply, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { editorHref, TemplateCard } from "@/components/automations/TemplateGallery";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardInset } from "@/components/ui/card";
import { DisabledReason } from "@/components/ui/disabled-reason";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useAutomation, useAutomationTemplates } from "@/lib/api/queries";
import { useAddCommentAutomation } from "@/lib/api/queries/scheduledPosts";
import type { AutomationTemplate, Plan, SocialAccount } from "@/lib/api/types";
import { DEFAULT_NAME, isCommentTrigger } from "@/lib/automations/definition";
import { STATUS_LABEL, TRIGGER_LABEL } from "@/lib/automations/format";
import { toastError } from "@/lib/toast-error";
import { handleOf } from "@/lib/publishing/rules";
import type { LinkedAutomation } from "@/lib/publishing/types";
import { cn } from "@/lib/utils";

import { Section } from "./Section";

const STATUS_TONE = { draft: "neutral", active: "success", paused: "warning" } as const;

/**
 * UX-SCR-13 Automation (FR-AUT-18): comment automations scoped to this post, with a summary and a
 * link to each, and "Add comment automation", which creates one from a template for one of the
 * post's accounts and opens it in the editor. It links itself to the post when it goes live.
 */
export function AutomationSection({
  wid,
  slug,
  postId,
  linked,
  accounts,
  plan,
  readOnly,
  beforeCreate,
}: {
  wid: string;
  slug: string;
  postId: string;
  linked: LinkedAutomation[];
  /** The post's accounts that can publish. */
  accounts: SocialAccount[];
  plan: Plan;
  readOnly: boolean;
  /** Resolves true once the post on screen is saved: the editor opens next, and leaving would drop unsaved edits. */
  beforeCreate: () => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const noAccount = accounts.length === 0;
  return (
    <Section id="composer-automation" title="Automation (optional)">
      {linked.length > 0 ? (
        <ul className="mb-3 space-y-2" aria-label="Automations for this post">
          {linked.map((automation) => (
            <LinkedRow key={automation.id} wid={wid} slug={slug} automation={automation} />
          ))}
        </ul>
      ) : (
        <p className="mb-3 text-sm text-fg-secondary">
          Answer the first comments on this post automatically, for example with a DM to everyone who comments a keyword.
        </p>
      )}
      {readOnly ? null : (
        <div className="flex flex-wrap items-center gap-2">
          <DisabledReason reason={noAccount ? "Choose an account first." : null}>
            <Button type="button" variant="secondary" size="lg" disabled={noAccount} onClick={() => setOpen(true)}>
              <Plus aria-hidden /> Add comment automation
            </Button>
          </DisabledReason>
        </div>
      )}
      {open ? (
        <AddAutomationDialog
          open={open}
          onOpenChange={setOpen}
          wid={wid}
          slug={slug}
          postId={postId}
          accounts={accounts}
          plan={plan}
          beforeCreate={beforeCreate}
        />
      ) : null}
    </Section>
  );
}

function LinkedRow({ wid, slug, automation }: { wid: string; slug: string; automation: LinkedAutomation }) {
  // The full automation adds the keywords and the action to the summary.
  const details = useAutomation(wid, automation.id).data;
  const trigger = details?.trigger ?? automation.trigger ?? null;
  const keywords = details?.keywords ?? [];
  const action = details?.action === "ai_reply" ? "AI reply" : details?.action === "send_message" ? "DM" : null;
  const summary = [
    trigger ? TRIGGER_LABEL[trigger] : "No trigger yet",
    keywords.length ? keywords.map((keyword) => keyword.toUpperCase()).join(", ") : null,
  ]
    .filter(Boolean)
    .join(": ");
  return (
    <CardInset asChild padding="compact">
     <li className="flex items-center gap-3">
      <MessageSquareReply className="size-4 shrink-0 text-fg-secondary" aria-hidden />
      <div className="min-w-0 flex-1">
        <Link href={editorHref(slug, automation.id)} className="block truncate text-sm font-medium hover:underline">
          {automation.name}
        </Link>
        <p className="truncate text-xs text-fg-secondary">
          {summary}
          {action ? ` → ${action}` : ""}
        </p>
      </div>
      <Badge tone={STATUS_TONE[automation.status]} size="md">
        {STATUS_LABEL[automation.status]}
      </Badge>
     </li>
    </CardInset>
  );
}

type Choice = AutomationTemplate | null;

function AddAutomationDialog({
  open,
  onOpenChange,
  wid,
  slug,
  postId,
  accounts,
  plan,
  beforeCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  wid: string;
  slug: string;
  postId: string;
  accounts: SocialAccount[];
  plan: Plan;
  beforeCreate: () => Promise<boolean>;
}) {
  const router = useRouter();
  const templates = useAutomationTemplates(wid);
  const add = useAddCommentAutomation(wid, postId);
  const [asking, setAsking] = useState<{ choice: Choice } | null>(null);
  const [accountId, setAccountId] = useState<string>(accounts[0]?.id ?? "");
  const commentTemplates = (templates.data ?? []).filter((template) => isCommentTrigger(template.trigger));

  const start = async (choice: Choice, account: string) => {
    if (!(await beforeCreate())) {
      toast.error("Your changes to this post aren't saved yet. Save them first, then add the automation.");
      return;
    }
    add.mutate(
      { templateKey: choice?.key ?? null, accountId: account, name: DEFAULT_NAME },
      {
        onSuccess: (automation) => {
          onOpenChange(false);
          router.push(editorHref(slug, automation.id, true));
        },
        // A plan limit (402) is the upgrade dialog's to explain: one message.
        onError: (error) => toastError(error),
      },
    );
  };

  const choose = (choice: Choice) => {
    if (accounts.length > 1) setAsking({ choice });
    else void start(choice, accounts[0].id);
  };

  const pendingKey = add.isPending ? (add.variables?.templateKey ?? "blank") : null;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setAsking(null);
        onOpenChange(next);
      }}
    >
      <DialogContent size="xl">
        {asking ? (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void start(asking.choice, accountId);
            }}
          >
            <DialogHeader>
              <DialogTitle>Which account?</DialogTitle>
              <DialogDescription>The automation answers comments on this post from one account.</DialogDescription>
            </DialogHeader>
            <fieldset className="space-y-2">
              <legend className="sr-only">Instagram account</legend>
              {accounts.map((account) => (
                <label
                  key={account.id}
                  className={cn(
                    "flex min-h-10 cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm",
                    accountId === account.id ? "border-brand bg-brand-soft" : "border-line hover:bg-hover",
                  )}
                >
                  <input
                    type="radio"
                    name="post-automation-account"
                    value={account.id}
                    checked={accountId === account.id}
                    onChange={() => setAccountId(account.id)}
                    className="accent-brand"
                  />
                  <span className="font-medium">{handleOf(account)}</span>
                </label>
              ))}
            </fieldset>
            <div className="flex justify-between gap-2">
              <Button type="button" variant="ghost" onClick={() => setAsking(null)}>
                <ArrowLeft aria-hidden /> Back
              </Button>
              <Button type="submit" disabled={!accountId} loading={add.isPending}>
                {asking.choice ? "Use template" : "Start from blank"}
              </Button>
            </div>
          </form>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Add comment automation</DialogTitle>
              <DialogDescription>
                It answers comments on this post and switches on when the post goes live. Pick a template and change anything.
              </DialogDescription>
            </DialogHeader>
            <ul aria-label="Templates" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {templates.isPending
                ? Array.from({ length: 3 }, (_, index) => (
                    <li key={index} aria-hidden>
                      <Skeleton className="h-44 rounded-xl" />
                    </li>
                  ))
                : commentTemplates.map((template) => (
                    <li key={template.key}>
                      <TemplateCard
                        template={template}
                        showPro={template.requires_paid_plan && plan === "free"}
                        pending={pendingKey === template.key}
                        disabled={add.isPending}
                        onUse={() => choose(template)}
                      />
                    </li>
                  ))}
              <li>
                <div className="flex h-full min-h-44 flex-col rounded-xl border border-dashed border-line-strong p-4">
                  <span className="grid size-9 place-items-center rounded-lg bg-raised text-fg-secondary">
                    <Sparkles className="size-5" aria-hidden />
                  </span>
                  <p className="mt-3 text-sm font-semibold">Start from blank</p>
                  <p className="mt-1 flex-1 text-sm text-fg-secondary">Choose the keywords and the reply yourself.</p>
                  <Button variant="secondary" className="mt-3 self-start" disabled={add.isPending} loading={pendingKey === "blank"} onClick={() => choose(null)}>
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
