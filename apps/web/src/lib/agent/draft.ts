/**
 * An automation draft prepared by Ask Social Hood (FR-AGT-03, AutomationDraftPrefill) laid over a
 * newly created automation's definition, in the editor's own terms (lib/automations/definition).
 * The result is what the editor's autosave would send; the member finishes it there.
 */
import type { AutomationDefinition, AutomationDraftPrefill, SocialAccount } from "@/lib/api/types";
import { toRequestBody, triggerPatch } from "@/lib/automations/definition";

export function definitionFromDraft(base: AutomationDefinition, draft: AutomationDraftPrefill): AutomationDefinition {
  let next: AutomationDefinition = { ...base, name: draft.name.trim() || base.name };
  if (draft.trigger && draft.trigger !== base.trigger) next = { ...next, ...triggerPatch(next, draft.trigger) };
  if (draft.keywords && draft.keywords.length > 0) next.keywords = [...draft.keywords];
  if (draft.action) next.action = draft.action;
  if (draft.message_text) next.message_text = draft.message_text;
  if (draft.ai_instructions) next.ai_instructions = draft.ai_instructions;
  if (draft.public_reply_texts && draft.public_reply_texts.length > 0) {
    next.public_reply_texts = [...draft.public_reply_texts];
  }
  // Any comment needs chosen posts or the next post (FR-AUT-02); "all" there keeps the editor's default.
  if (!(draft.post_scope === "all" && next.trigger === "comment_any")) next.post_scope = draft.post_scope;
  if (draft.media_item_ids && draft.media_item_ids.length > 0) next.media_item_ids = [...draft.media_item_ids];
  return toRequestBody(next);
}

/** The account the draft names when it can run there, the only account, or none yet. */
export function draftAccount(draft: AutomationDraftPrefill, accounts: SocialAccount[]): string | null {
  if (draft.social_account_id && accounts.some((account) => account.id === draft.social_account_id)) {
    return draft.social_account_id;
  }
  return accounts.length === 1 ? accounts[0].id : null;
}
