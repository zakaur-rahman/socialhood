"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { toApiError, type ApiError } from "@/lib/api/errors";
import { useAutomationFlow, useSaveFlow } from "@/lib/api/queries";
import type { Automation, FlowDefinition } from "@/lib/api/types";
import { compile, decompile, placeErrors, type EditorStep, type StepErrors } from "@/lib/automations/flow";

import { AUTOSAVE_DELAY_MS, type SaveStatus } from "../use-autosave";

export type FlowDraft = {
  /** "off": the automation runs on its message settings; "opaque": a flow the editor can't show. */
  phase: "off" | "loading" | "error" | "opaque" | "ready";
  loadError: Error | null;
  retryLoad: () => void;
  /** The steps (empty unless ``phase`` is "ready"). */
  tree: EditorStep[];
  /** The tree as the stored graph, and the step id at each of its indexes. */
  definition: FlowDefinition | null;
  ids: string[];
  /** The stored flow, for a flow the editor can't show. */
  stored: FlowDefinition | null;
  update: (change: (tree: EditorStep[]) => EditorStep[]) => void;
  /** Start from a tree that is already saved (the automation was just converted). */
  begin: (tree: EditorStep[]) => void;
  flush: () => Promise<boolean>;
  status: SaveStatus;
  error: ApiError | null;
  /** The API's refusal of the last save, on the steps. */
  saveErrors: StepErrors;
  saveGeneral: string[];
  /** The plan's cap on steps was reached (402): said in plain words. */
  capMessage: string | null;
};

/**
 * GR-13: the flow of an automation saved as one. The tree is read from the stored flow once, then
 * the user's edits are the truth; every edit restarts a 1 s timer and the whole flow is PUT, as the
 * message settings are (use-autosave). Saves never overlap, pending edits are sent when the editor
 * unmounts or the tab closes, and "saved" shows only once the API has the latest edit.
 */
export function useFlowDraft(wid: string, automation: Automation, delay = AUTOSAVE_DELAY_MS): FlowDraft {
  const on = automation.flow_source === "flow";
  const query = useAutomationFlow(wid, automation.id, on);
  const save = useSaveFlow(wid, automation.id);

  // The stored definition as text, so a refetch with the same flow doesn't rebuild the tree.
  const raw = query.data ? JSON.stringify(query.data.definition) : null;
  const base = useMemo(() => (raw ? decompile(JSON.parse(raw) as FlowDefinition) : null), [raw]);
  const [edits, setEdits] = useState<EditorStep[] | null>(null);
  const tree = edits ?? base;

  const [status, setStatus] = useState<SaveStatus>("saved");
  const [error, setError] = useState<ApiError | null>(null);
  const [saveErrors, setSaveErrors] = useState<StepErrors>({});
  const [saveGeneral, setSaveGeneral] = useState<string[]>([]);

  const latest = useRef<EditorStep[] | null>(null);
  const baseRef = useRef<EditorStep[] | null>(null);
  const versions = useRef(0);
  const savedVersions = useRef(0);
  const timer = useRef<number | null>(null);
  const running = useRef<Promise<boolean> | null>(null);
  const mutate = useRef(save.mutateAsync);
  useEffect(() => {
    mutate.current = save.mutateAsync;
    baseRef.current = base;
  }, [save.mutateAsync, base]);

  const clearTimer = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  };

  const flush = useCallback(async (): Promise<boolean> => {
    clearTimer();
    while (running.current) await running.current;
    if (savedVersions.current === versions.current) return true;
    const version = versions.current;
    const current = latest.current;
    if (!current) return true;
    const compiled = compile(current);
    setStatus("saving");
    const attempt = (async () => {
      try {
        await mutate.current(compiled.definition);
        savedVersions.current = version;
        setError(null);
        setSaveErrors({});
        setSaveGeneral([]);
        if (versions.current === version) setStatus("saved");
        return versions.current === version;
      } catch (caught) {
        const failure = toApiError(caught);
        setError(failure);
        if (failure.code === "validation_error") {
          const placed = placeErrors(failure.errors, compiled.ids);
          setSaveErrors(placed.byStep);
          setSaveGeneral(placed.general);
        }
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
    (change: (tree: EditorStep[]) => EditorStep[]) => {
      const current = latest.current ?? baseRef.current;
      if (!current) return;
      const next = change(current);
      if (next === current) return;
      latest.current = next;
      setEdits(next);
      versions.current += 1;
      setStatus("saving");
      clearTimer();
      timer.current = window.setTimeout(() => {
        timer.current = null;
        void flush();
      }, delay);
    },
    [delay, flush],
  );

  const begin = useCallback((started: EditorStep[]) => {
    latest.current = started;
    setEdits(started);
    versions.current += 1;
    savedVersions.current = versions.current;
    setStatus("saved");
    setError(null);
  }, []);

  useEffect(
    () => () => {
      if (savedVersions.current !== versions.current) void flush();
    },
    [flush],
  );

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (savedVersions.current === versions.current && !running.current) return;
      void flush();
      event.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [flush]);

  const compiled = useMemo(() => (tree ? compile(tree) : null), [tree]);

  let phase: FlowDraft["phase"] = "off";
  if (on) {
    if (tree) phase = "ready";
    else if (query.isPending) phase = "loading";
    else if (query.isError) phase = "error";
    else phase = "opaque";
  }

  return {
    phase,
    loadError: query.error,
    retryLoad: () => void query.refetch(),
    tree: tree ?? [],
    definition: compiled?.definition ?? null,
    ids: compiled?.ids ?? [],
    stored: query.data?.definition ?? null,
    update,
    begin,
    flush,
    status,
    error,
    saveErrors,
    saveGeneral,
    capMessage: error?.code === "quota_exceeded" ? (error.detail ?? "Your plan has reached its limit on steps.") : null,
  };
}
