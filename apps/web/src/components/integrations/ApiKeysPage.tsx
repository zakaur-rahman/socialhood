"use client";

import type { Route } from "next";
import Link from "next/link";

import { ApiKeysSection } from "@/components/integrations/ApiKeysSection";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { siteHref } from "@/lib/marketing/site";

const LINK = "font-medium text-brand-fg underline underline-offset-4";

/**
 * Settings › API keys (C-165): the workspace's keys on their own page, not under Integrations. A
 * key works for the public API and, with the AI app scopes, for Claude Code, Codex and other
 * MCP apps. The Pro gate (the public_api entitlement) lives in ApiKeysSection. Owners and admins.
 */
export function ApiKeysPage() {
  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="API keys"
          description={
            <>
              Keys work for the{" "}
              <Link className={LINK} href={siteHref("/developers/api") as Route}>
                public API
              </Link>{" "}
              and for AI apps (MCP) such as Claude Code and Codex.{" "}
              <Link className={LINK} href={siteHref("/developers/mcp/api-key") as Route}>
                Connect an AI app with a key
              </Link>
              .
            </>
          }
        />
      }
    >
      <ApiKeysSection />
    </SettingsFrame>
  );
}
