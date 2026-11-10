"use client";

import { Bot, Copy } from "lucide-react";
import { toast } from "sonner";

import { SettingsCard } from "@/components/settings/SettingsCard";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { clientGuides, mcpUrl } from "@/lib/marketing/connect-ai";
import { cn } from "@/lib/utils";
import { MONO } from "@/styles/tokens";

/** Tab names: the guides' own names are long ("Claude (claude.ai, desktop and mobile)"). */
const TAB_LABEL: Record<string, string> = { claude: "Claude", "claude-code": "Claude Code", chatgpt: "ChatGPT", codex: "Codex" };
/** The guides that can use an API key instead of signing in. */
const KEY_GUIDES = new Set(["claude-code", "codex"]);

/**
 * C-180: how to connect Claude, ChatGPT or Codex, inside the app, so nobody leaves the dashboard
 * for the setup guide. The steps are /developers/mcp's (lib/marketing/connect-ai.ts), so the two
 * can't drift apart.
 */
export function SetupCard({ canMakeKeys }: { canMakeKeys: boolean }) {
  const guides = clientGuides(mcpUrl());
  return (
    <SettingsCard
      id="set-up"
      icon={<Bot />}
      title="Connect an AI app"
      description="Add Amplychat to your AI app once. It asks you to sign in here and choose what it may do."
    >
      <Tabs defaultValue={guides[0].id}>
        <TabsList aria-label="AI app">
          {guides.map((guide) => (
            <TabsTrigger key={guide.id} value={guide.id}>
              {TAB_LABEL[guide.id] ?? guide.name}
            </TabsTrigger>
          ))}
        </TabsList>
        {guides.map((guide) => (
          <TabsContent key={guide.id} value={guide.id} className="space-y-3">
            <p className="text-sm text-fg-secondary">{guide.who}</p>
            <ol className="list-decimal space-y-3 ps-5 text-sm marker:text-fg-secondary">
              {guide.steps.map((step) => (
                <li key={step.text} className="space-y-2 ps-1">
                  <p>{step.text}</p>
                  {step.code ? <CodeBlock code={step.code} /> : null}
                </li>
              ))}
            </ol>
            {guide.note ? <p className="text-xs text-fg-secondary">{guide.note}</p> : null}
            {KEY_GUIDES.has(guide.id) ? (
              <p className="text-xs text-fg-secondary">
                {canMakeKeys ? (
                  <a className="font-medium text-brand-fg underline underline-offset-4" href="#api-keys">
                    Create an API key below
                  </a>
                ) : (
                  "Owners and admins create API keys on this page."
                )}
              </p>
            ) : null}
          </TabsContent>
        ))}
      </Tabs>
    </SettingsCard>
  );
}

function CodeBlock({ code }: { code: string }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      toast.success("Copied");
    } catch {
      toast.error("Couldn't copy. Select the text and copy it by hand.");
    }
  }
  return (
    <div className="flex items-start gap-2">
      <pre tabIndex={0} className={cn(MONO, "min-w-0 flex-1 overflow-x-auto rounded-lg bg-field p-3 whitespace-pre-wrap break-all")}>
        {code}
      </pre>
      <Button type="button" variant="ghost" size="icon-sm" aria-label="Copy" onClick={() => void copy()}>
        <Copy aria-hidden />
      </Button>
    </div>
  );
}
