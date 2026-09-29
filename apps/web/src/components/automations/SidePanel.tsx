"use client";

import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AutomationDefinition } from "@/lib/api/types";
import { usesFollowNudge, usesTapFirst } from "@/lib/automations/definition";

import { MatchTester } from "./MatchTester";
import { PreviewPane } from "./PreviewPane";
import { RunsPane } from "./RunsPane";
import { StatsPane } from "./StatsPane";

type Tab = "preview" | "test" | "runs" | "stats";

/**
 * UX-SCR-03 right panel: Preview, Test, Runs and Stats. At ≥ 1280 px it is a 340 px sticky column;
 * below that the editor places it above the steps. A tab's content mounts (and loads) when opened.
 */
export function SidePanel({
  wid,
  slug,
  automationId,
  draft,
  accountUsername,
  disclosure,
  mediaUrl,
  timeZone,
  beforeTest,
}: {
  wid: string;
  slug: string;
  automationId: string;
  draft: AutomationDefinition;
  accountUsername: string | null;
  disclosure: string | null;
  mediaUrl: string | null;
  timeZone: string;
  beforeTest: () => Promise<boolean>;
}) {
  const [tab, setTab] = useState<Tab>("preview");
  return (
    <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
      <TabsList aria-label="Automation panel">
        <TabsTrigger value="preview">Preview</TabsTrigger>
        <TabsTrigger value="test">Test</TabsTrigger>
        <TabsTrigger value="runs">Runs</TabsTrigger>
        <TabsTrigger value="stats">Stats</TabsTrigger>
      </TabsList>
      <TabsContent value="preview">
        <PreviewPane draft={draft} accountUsername={accountUsername} disclosure={disclosure} mediaUrl={mediaUrl} />
      </TabsContent>
      <TabsContent value="test">
        <MatchTester
          wid={wid}
          automationId={automationId}
          trigger={draft.trigger}
          openingButton={draft.opening_button}
          beforeTest={beforeTest}
        />
      </TabsContent>
      <TabsContent value="runs">
        <RunsPane wid={wid} slug={slug} automationId={automationId} timeZone={timeZone} />
      </TabsContent>
      <TabsContent value="stats">
        <StatsPane
          wid={wid}
          automationId={automationId}
          tapFirst={usesTapFirst(draft)}
          followNudge={usesFollowNudge(draft)}
        />
      </TabsContent>
    </Tabs>
  );
}
