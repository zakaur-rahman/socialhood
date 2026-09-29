"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { toApiError, type ApiError } from "@/lib/api/errors";
import { useSaveScheduledPost } from "@/lib/api/queries/scheduledPosts";
import type { ScheduledPost, ScheduledPostDraft } from "@/lib/publishing/types";

export const AUTOSAVE_DELAY_MS = 1000;

/**
 * "saved": the API has the latest edit. "saving": an edit is waiting for or in its save.
 * "unsaved": a scheduled post's edits wait for Update schedule. "error": the last save failed.
 */
export type PostSaveStatus = "saved" | "saving" | "unsaved" | "error";

export type Draft = {
  targets: { social_account_id: string; caption_override: string | null }[];
  asset_ids: string[];
  caption: string;
  first_comment: string | null;
  publish_at: string | null;
};

/** The editable fields of a stored post, assets in their order. */
export function toDraft(post: ScheduledPost): Draft {
  return {
    targets: post.targets.map((target) => ({
      social_account_id: target.social_account_id,
      caption_override: target.caption_override ?? null,
    })),
    asset_ids: [...post.assets].sort((a, b) => a.position - b.position).map((asset) => asset.id),
    caption: post.caption,
    first_comment: post.first_comment ?? null,
    publish_at: post.publish_at ?? null,
  };
}

/** What the PUT sends: an empty first comment is no first comment. */
export function toRequest(draft: Draft): ScheduledPostDraft {
  return {
    targets: draft.targets.map((target) => ({ ...target })),
    asset_ids: [...draft.asset_ids],
    caption: draft.caption,
    first_comment: draft.first_comment?.trim() ? draft.first_comment : null,
    publish_at: draft.publish_at,
  };
}

type Patch = Partial<Draft> | ((draft: Draft) => Partial<Draft>);

/**
 * The composer's draft (F-13). A draft autosaves: every edit restarts a 1 s timer, then the whole
 * post is PUT; saves never overlap, and an edit made during a save is sent after it. A scheduled
 * post doesn't autosave: its edits wait for Update schedule, because a PUT changes what will be
 * published. Pending autosaves are sent when the composer unmounts; closing the tab with unsaved
 * edits asks first.
 */
export function usePostDraft(
  wid: string,
  initial: ScheduledPost,
  { autosave, delay = AUTOSAVE_DELAY_MS }: { autosave: boolean; delay?: number },
) {
  const save = useSaveScheduledPost(wid, initial.id);
  const [draft, setDraft] = useState<Draft>(() => toDraft(initial));
  const [status, setStatus] = useState<PostSaveStatus>("saved");
  const [error, setError] = useState<ApiError | null>(null);

  const latest = useRef(draft);
  const edits = useRef(0);
  const savedEdits = useRef(0);
  const timer = useRef<number | null>(null);
  const running = useRef<Promise<ScheduledPost | null> | null>(null);
  const autosaveRef = useRef(autosave);
  const mutate = useRef(save.mutateAsync);
  useEffect(() => {
    mutate.current = save.mutateAsync;
    autosaveRef.current = autosave;
  }, [save.mutateAsync, autosave]);

  const clearTimer = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  };

  /**
   * Save now if anything is unsaved (or always, with force). Resolves with the stored post once
   * the latest edit is saved, or null when the save failed.
   */
  const flush = useCallback(async ({ force = false }: { force?: boolean } = {}): Promise<ScheduledPost | null> => {
    clearTimer();
    while (running.current) await running.current;
    if (!force && savedEdits.current === edits.current) return null;
    const version = edits.current;
    setStatus("saving");
    const attempt = (async () => {
      try {
        const post = await mutate.current(toRequest(latest.current));
        savedEdits.current = Math.max(savedEdits.current, version);
        setError(null);
        if (edits.current === version) setStatus("saved");
        else setStatus(autosaveRef.current ? "saving" : "unsaved");
        return post;
      } catch (caught) {
        setError(toApiError(caught));
        setStatus("error");
        return null;
      }
    })();
    running.current = attempt;
    try {
      return await attempt;
    } finally {
      if (running.current === attempt) running.current = null;
    }
  }, []);

  /** Save what's pending, and say whether the API has everything now. */
  const settle = useCallback(async (): Promise<boolean> => {
    if (savedEdits.current === edits.current && !running.current) return true;
    await flush();
    return savedEdits.current === edits.current;
  }, [flush]);

  const update = useCallback(
    (patch: Patch) => {
      const change = typeof patch === "function" ? patch(latest.current) : patch;
      const next = { ...latest.current, ...change };
      latest.current = next;
      setDraft(next);
      edits.current += 1;
      clearTimer();
      if (!autosaveRef.current) {
        setStatus("unsaved");
        return;
      }
      setStatus("saving");
      timer.current = window.setTimeout(() => {
        timer.current = null;
        void flush();
      }, delay);
    },
    [delay, flush],
  );

  /** Take the stored post as the draft (after Schedule, queue or Edit and retry). */
  const reset = useCallback((post: ScheduledPost) => {
    clearTimer();
    const next = toDraft(post);
    latest.current = next;
    setDraft(next);
    savedEdits.current = edits.current;
    setError(null);
    setStatus("saved");
  }, []);

  /** Forget unsaved edits (the post was deleted, or publishing started). */
  const discard = useCallback(() => {
    clearTimer();
    savedEdits.current = edits.current;
    setStatus("saved");
  }, []);

  // A scheduled post that becomes a draft again starts autosaving what is pending.
  useEffect(() => {
    if (autosave && savedEdits.current !== edits.current && !running.current && timer.current === null) {
      timer.current = window.setTimeout(() => {
        timer.current = null;
        void flush();
      }, delay);
    }
  }, [autosave, delay, flush]);

  // Leaving the composer inside the app: a draft's pending edits are sent, not dropped.
  useEffect(
    () => () => {
      if (autosaveRef.current && savedEdits.current !== edits.current) void flush();
    },
    [flush],
  );

  // Closing or reloading the tab with unsaved edits: a draft starts its save; either way the
  // browser asks before leaving.
  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (savedEdits.current === edits.current && !running.current) return;
      if (autosaveRef.current) void flush();
      event.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [flush]);

  const dirty = status !== "saved";
  return { draft, update, flush, settle, reset, discard, status, error, dirty };
}
