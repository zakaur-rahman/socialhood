"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { toApiError, type ApiError } from "@/lib/api/errors";
import { useSaveAutomation } from "@/lib/api/queries";
import type { Automation, AutomationDefinition } from "@/lib/api/types";
import { toDefinition, toRequestBody } from "@/lib/automations/definition";

export const AUTOSAVE_DELAY_MS = 1000;

/** "saving" from the first unsaved edit until the API confirms it; "error" when the PUT failed. */
export type SaveStatus = "saved" | "saving" | "error";

/**
 * F-11 autosave: every edit restarts a 1 s timer, then the whole definition is PUT. Saves never
 * overlap: an edit made during a save is sent after it. Pending edits are saved when the editor
 * unmounts (navigating away inside the app) and when the tab closes, where the browser also asks
 * before leaving. "Saved" shows only once the API has confirmed the latest edit.
 */
export function useAutosave(wid: string, automation: Automation, delay = AUTOSAVE_DELAY_MS) {
  const save = useSaveAutomation(wid, automation.id);
  const [draft, setDraft] = useState<AutomationDefinition>(() => toDefinition(automation));
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [error, setError] = useState<ApiError | null>(null);

  const latest = useRef(draft);
  const edits = useRef(0);
  const savedEdits = useRef(0);
  const timer = useRef<number | null>(null);
  const running = useRef<Promise<boolean> | null>(null);
  const mutate = useRef(save.mutateAsync);
  useEffect(() => {
    mutate.current = save.mutateAsync;
  }, [save.mutateAsync]);

  const clearTimer = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  };

  /** Save now if anything is unsaved. Resolves true once the latest edit is stored. */
  const flush = useCallback(async (): Promise<boolean> => {
    clearTimer();
    while (running.current) await running.current;
    if (savedEdits.current === edits.current) return true;
    const version = edits.current;
    setStatus("saving");
    const attempt = (async () => {
      try {
        await mutate.current(toRequestBody(latest.current));
        savedEdits.current = version;
        setError(null);
        if (edits.current === version) setStatus("saved");
        return edits.current === version;
      } catch (caught) {
        setError(toApiError(caught));
        setStatus("error");
        return false;
      }
    })();
    running.current = attempt;
    try {
      return await attempt;
    } finally {
      if (running.current === attempt) running.current = null;
    }
  }, []);

  const update = useCallback(
    (patch: Partial<AutomationDefinition>) => {
      const next = { ...latest.current, ...patch };
      latest.current = next;
      setDraft(next);
      edits.current += 1;
      setStatus("saving");
      clearTimer();
      timer.current = window.setTimeout(() => {
        timer.current = null;
        void flush();
      }, delay);
    },
    [delay, flush],
  );

  /** Forget unsaved edits (the automation was deleted). */
  const discard = useCallback(() => {
    clearTimer();
    savedEdits.current = edits.current;
  }, []);

  // Leaving the editor inside the app: send what is pending instead of dropping it.
  useEffect(
    () => () => {
      if (savedEdits.current !== edits.current) void flush();
    },
    [flush],
  );

  // Closing or reloading the tab: start the save and ask the browser to confirm leaving.
  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (savedEdits.current === edits.current && !running.current) return;
      void flush();
      event.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [flush]);

  return { draft, update, flush, discard, status, error };
}
