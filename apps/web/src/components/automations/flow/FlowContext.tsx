"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import type { FlowFieldDefinition, FlowTag } from "@/lib/api/types";
import {
  endsFlow,
  flatten,
  locate,
  makeStep,
  move,
  removeStep,
  stepIds,
  stepProblems,
  updateList,
  updateStep,
  type EditorStep,
  type ListRef,
  type StepKind,
  type StepErrors,
} from "@/lib/automations/flow";

import type { Uploader } from "../steps/ThenStep";

/** One problem on a step's field. ``hard`` ones come from the API and are always shown. */
export type FieldProblem = { message: string; hard: boolean };

export type FlowEnv = {
  wid: string;
  disclosure: string | null;
  comment: boolean;
  upload?: Uploader;
  tags: FlowTag[];
  fields: FlowFieldDefinition[];
  tree: EditorStep[];
  numberOf: (id: string) => number;
  /** The id of the first step: a comment's private reply, which can't carry an image. */
  firstId: string | null;
  /** The problems on a step, by field: the API's, and the editor's once the step has been touched. */
  problemsOf: (id: string) => Record<string, FieldProblem>;
  /** A step is complete, not finished (nothing wrong yet, but something to fill in), or needs attention. */
  stateOf: (id: string) => "complete" | "incomplete" | "error";
  /** Every step with a problem the user should see, in order. */
  attention: { id: string; number: number; title: string; message: string }[];
  patch: (id: string, change: (node: EditorStep) => EditorStep) => void;
  add: (ref: ListRef, kind: StepKind) => void;
  remove: (id: string) => void;
  moveBy: (id: string, delta: -1 | 1) => void;
  reorder: (ref: ListRef, from: number, to: number) => void;
  /** The same change on a list in the tree (an arm). */
  editList: (ref: ListRef, change: (steps: EditorStep[]) => EditorStep[]) => void;
  collapsed: ReadonlySet<string>;
  toggleCollapsed: (id: string) => void;
  /** True once for a step just added, so its card takes focus. */
  claimFocus: (id: string) => boolean;
  /** Steps in the flow, and the plan's most (null: no cap). */
  count: number;
  cap: number | null;
  announce: (message: string) => void;
};

const FlowCtx = createContext<FlowEnv | null>(null);

export function useFlowEnv(): FlowEnv {
  const env = useContext(FlowCtx);
  if (!env) throw new Error("useFlowEnv outside a FlowProvider");
  return env;
}

export function FlowProvider({
  wid,
  tree,
  update,
  disclosure,
  comment,
  upload,
  tags,
  fields,
  serverErrors,
  clearServerErrors,
  cap,
  onAnnounce,
  title,
  children,
}: {
  wid: string;
  tree: EditorStep[];
  update: (change: (tree: EditorStep[]) => EditorStep[]) => void;
  disclosure: string | null;
  comment: boolean;
  upload?: Uploader;
  tags: FlowTag[];
  fields: FlowFieldDefinition[];
  /** The API's problems (a refused save, a refused activation), by step. */
  serverErrors: StepErrors;
  clearServerErrors: (id: string) => void;
  cap: number | null;
  onAnnounce: (message: string) => void;
  title: (node: EditorStep) => string;
  children: ReactNode;
}) {
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const focus = useRef<string | null>(null);

  const context = useMemo(
    () => ({
      disclosure,
      fields: fields.map((field) => ({ key: field.key, type: field.type })),
      tagIds: new Set(tags.map((tag) => tag.id)),
    }),
    [disclosure, fields, tags],
  );
  const order = useMemo(() => flatten(tree), [tree]);
  const numbers = useMemo(() => new Map(order.map((node, index) => [node.id, index + 1])), [order]);

  const touch = useCallback((id: string) => setTouched((current) => (current.has(id) ? current : new Set(current).add(id))), []);

  const problemsOf = useCallback(
    (id: string): Record<string, FieldProblem> => {
      const out: Record<string, FieldProblem> = {};
      const node = order.find((item) => item.id === id);
      if (node && touched.has(id)) {
        for (const [field, message] of Object.entries(stepProblems(node, context))) out[field] = { message, hard: false };
      }
      for (const [field, message] of Object.entries(serverErrors[id] ?? {})) out[field] = { message, hard: true };
      return out;
    },
    [order, touched, context, serverErrors],
  );

  const stateOf = useCallback(
    (id: string): "complete" | "incomplete" | "error" => {
      if (Object.keys(problemsOf(id)).length > 0) return "error";
      const node = order.find((item) => item.id === id);
      return node && Object.keys(stepProblems(node, context)).length > 0 ? "incomplete" : "complete";
    },
    [problemsOf, order, context],
  );

  const attention = useMemo(
    () =>
      order.flatMap((node) => {
        const found = Object.values(problemsOf(node.id));
        return found.slice(0, 1).map((problem) => ({
          id: node.id,
          number: numbers.get(node.id) ?? 0,
          title: title(node),
          message: problem.message,
        }));
      }),
    [order, problemsOf, numbers, title],
  );

  const patch = useCallback(
    (id: string, change: (node: EditorStep) => EditorStep) => {
      touch(id);
      clearServerErrors(id);
      update((current) => updateStep(current, id, change));
    },
    [update, touch, clearServerErrors],
  );

  const add = useCallback(
    (ref: ListRef, kind: StepKind) => {
      let added = "";
      update((current) => {
        if (countOf(current) >= (cap ?? Infinity)) return current;
        const node = makeStep(kind, stepIds(current));
        added = node.id;
        return updateList(current, ref, (steps) => (endsFlow(steps[steps.length - 1]) ? steps : [...steps, node]));
      });
      if (added) focus.current = added;
    },
    [update, cap],
  );

  const remove = useCallback(
    (id: string) => {
      clearServerErrors(id);
      update((current) => {
        const where = locate(current, id);
        // A flow always has its first step: the last one in the root list stays.
        if (!where || (where.ref.parent === null && where.length === 1)) return current;
        return removeStep(current, id);
      });
    },
    [update, clearServerErrors],
  );

  const reorder = useCallback(
    (ref: ListRef, from: number, to: number) => {
      update((current) => updateList(current, ref, (steps) => move(steps, from, to)));
    },
    [update],
  );

  const moveBy = useCallback(
    (id: string, delta: -1 | 1) => {
      const where = locate(tree, id);
      if (!where) return;
      const target = where.index + delta;
      if (target < 0 || target >= where.length) return;
      reorder(where.ref, where.index, target);
      onAnnounce(`Moved step ${numbers.get(id) ?? ""} ${delta < 0 ? "up" : "down"}`.replace("  ", " "));
    },
    [tree, reorder, onAnnounce, numbers],
  );

  const editList = useCallback(
    (ref: ListRef, change: (steps: EditorStep[]) => EditorStep[]) => update((current) => updateList(current, ref, change)),
    [update],
  );

  const toggleCollapsed = useCallback(
    (id: string) =>
      setCollapsed((current) => {
        const next = new Set(current);
        if (!next.delete(id)) next.add(id);
        return next;
      }),
    [],
  );

  const claimFocus = useCallback((id: string) => {
    if (focus.current !== id) return false;
    focus.current = null;
    return true;
  }, []);

  const env: FlowEnv = {
    wid,
    disclosure,
    comment,
    upload,
    tags,
    fields,
    tree,
    numberOf: (id) => numbers.get(id) ?? 0,
    firstId: tree[0]?.id ?? null,
    problemsOf,
    stateOf,
    attention,
    patch,
    add,
    remove,
    moveBy,
    reorder,
    editList,
    collapsed,
    toggleCollapsed,
    claimFocus,
    count: order.length,
    cap,
    announce: onAnnounce,
  };
  return <FlowCtx.Provider value={env}>{children}</FlowCtx.Provider>;
}

function countOf(tree: EditorStep[]): number {
  return flatten(tree).length;
}
