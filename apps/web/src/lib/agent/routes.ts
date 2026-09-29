/**
 * Where citations and action cards lead (FR-AGT-01, FR-AGT-03). Paths are relative to the
 * workspace (/w/{slug}/), as the API gives action routes.
 */
import type { Route } from "next";

import type { ActionCard, AnswerRef } from "@/lib/api/types";

/**
 * The screen a cited record opens. A comment and a scheduled message have no screen of their own:
 * they open their post and their conversation (the reference's parent), or the Comments page and
 * the inbox when it names none.
 */
export function refPath(ref: AnswerRef): string {
  switch (ref.kind) {
    case "post":
      return `comments/${ref.id}`;
    case "conversation":
      return `inbox/${ref.id}`;
    case "comment":
      return ref.parent_id ? `comments/${ref.parent_id}` : "comments";
    case "automation":
      return `automations/${ref.id}`;
    case "scheduled_message":
      return ref.parent_id ? `inbox/${ref.parent_id}` : "inbox";
    case "scheduled_post":
      return `schedule/${ref.id}`;
    case "knowledge_source":
      return "knowledge";
  }
}

// A path of plain segments and an optional query: no scheme, host, "..", fragment or "//".
const SAFE_PATH = /^[A-Za-z0-9_-]+(\/[A-Za-z0-9_-]+)*(\?[A-Za-z0-9_\-=&%.,:+]*)?$/;

/** The card's route when it is a plain workspace path, else the screen its prefill names. */
export function actionPath(card: ActionCard): string {
  const route = card.route.trim().replace(/^\/+/, "");
  if (SAFE_PATH.test(route)) return route;
  switch (card.kind) {
    case "schedule_message":
      return `inbox/${card.prefill.conversation_id}?schedule=1`;
    case "reply_to_comment":
      return `comments/${card.prefill.post_id}`;
    case "automation_draft":
      return "automations/new";
  }
}

/** Typed routes can't check a path built at run time; workspace links are cast here, once. */
export function workspaceHref(slug: string, path: string): Route {
  return `/w/${slug}/${path}` as Route;
}

export function askHref(slug: string): Route {
  return workspaceHref(slug, "ask");
}

/** The full Ask page, where the shortcut and the top-bar button focus its question box instead. */
export function isAskPage(pathname: string | null | undefined): boolean {
  return /^\/w\/[^/]+\/ask\/?$/.test(pathname ?? "");
}

export function agentSettingsHref(slug: string): Route {
  return workspaceHref(slug, "settings/agent");
}
