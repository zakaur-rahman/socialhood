/**
 * The flow editor's model (GR-13). The API stores a flow as a graph of steps that point at each
 * other (services/automations/flows.py); the editor works on a tree, because a vertical list with
 * indented groups is what fits a phone:
 *
 * - a list of steps runs top to bottom: each step's "next" is the step below it;
 * - a step that forks (quick replies, a question that can fail, a branch, a split) has arms, each
 *   its own list of steps. When an arm runs out it carries on with the step below the forking
 *   step, so branches meet again; an arm that should stop ends with an End step. An empty arm with
 *   nothing below the fork simply ends.
 *
 * ``compile`` turns the tree into the stored graph, ``decompile`` reads a stored graph back. A
 * graph the tree can't show (steps shared by paths that never meet, made outside the editor)
 * decompiles to null; the editor then shows it read-only.
 */
import type { ProblemField } from "@/lib/api/errors";
import type {
  FlowAction,
  FlowButton,
  FlowCondition,
  FlowDefinition,
  FlowPreviewStep,
  FlowStep,
  Platform,
} from "@/lib/api/types";

import { messageLimit, messageSize, networkName, overLimitCopy } from "./limits";
import {
  BUTTON_TEXT_MAX_CHARS,
  renderFields,
  withDisclosure,
  worstCaseChars,
  type FieldValues,
} from "./render";

// ---------------------------------------------------------------- the tree

export type TypedAnswer = { mode: "none" } | { mode: "same"; index: number } | { mode: "own"; steps: EditorStep[] };

export type Reply = { title: string; steps: EditorStep[] };
export type Rule = { when: FlowCondition; steps: EditorStep[] };
export type SplitPath = { weight: number; steps: EditorStep[] };

export type SendNode = {
  kind: "send";
  id: string;
  text: string;
  image_asset_id: string | null;
  /** Where the image is shown (not stored): the editor remembers what it just uploaded. */
  image_url?: string | null;
  buttons: FlowButton[];
  replies: Reply[];
  typed: TypedAnswer;
  /**
   * GR-21: send a saved reply instead of writing the message. ``saved`` is the choice, so it holds
   * before a reply is picked; the reply goes alone (no text, image, buttons or quick replies).
   */
  saved?: boolean;
  saved_reply_id?: string | null;
};
/** GR-31: send a product from the catalogue (name, price, stock when recorded, picture and link, read when the step runs). */
export type ProductNode = {
  kind: "product";
  id: string;
  product_id: string | null;
  /** One variant (size, colour…), or null for the product: its price, or a short list of its variants. */
  variant_id: string | null;
  /** A line of your own above it. */
  intro: string;
};
export type AskNode = {
  kind: "ask";
  id: string;
  text: string;
  expect: "text" | "email" | "phone";
  field_key: string | null;
  retry_text: string;
  tries: number;
  /** Ask a marketing consent question after the answer is saved (recorded with the messages as evidence). */
  consent: boolean;
  consent_text: string;
  /** Sent once the answer is saved; blank sends nothing. */
  confirm_text: string;
  /** Null ends the flow when the answer never fits; steps (possibly none) go on from there. */
  skip: EditorStep[] | null;
};
export type BranchNode = { kind: "branch"; id: string; rules: Rule[]; otherwise: EditorStep[] };
export type ActionNode = { kind: "action"; id: string; action: FlowAction };
export type DelayNode = { kind: "delay"; id: string; seconds: number };
export type SplitNode = { kind: "split"; id: string; paths: SplitPath[] };
export type AiNode = { kind: "ai"; id: string; instructions: string };
export type EndNode = { kind: "end"; id: string };

export type EditorStep = SendNode | ProductNode | AskNode | BranchNode | ActionNode | DelayNode | SplitNode | AiNode | EndNode;
export type StepKind = EditorStep["kind"];

/** What the "Add step" menu offers, in order. AI replies are chosen above the steps. */
export const ADDABLE: { kind: Exclude<StepKind, "ai">; label: string; hint: string }[] = [
  { kind: "send", label: "Send", hint: "A message, with an image, link buttons or quick replies" },
  { kind: "product", label: "Product", hint: "Send a product from your catalogue with its price and link" },
  { kind: "ask", label: "Ask", hint: "Ask a question and save the answer" },
  { kind: "branch", label: "Branch", hint: "Go different ways by a tag, a field or who they are" },
  { kind: "action", label: "Action", hint: "Tag them, set a field, tell the team or hand off" },
  { kind: "delay", label: "Delay", hint: "Wait before the next step" },
  { kind: "split", label: "Split", hint: "Send people down different paths at random" },
  { kind: "end", label: "End", hint: "Stop the flow here" },
];

export const KIND_LABEL: Record<StepKind, string> = {
  send: "Send",
  product: "Product",
  ask: "Ask",
  branch: "Branch",
  action: "Action",
  delay: "Delay",
  split: "Split",
  ai: "AI reply",
  end: "End",
};

export const MAX_STEPS = 50;
/** Most quick replies a message takes, and paths a split takes (the API's limits). */
export const MAX_REPLIES = 13;
export const MAX_PATHS = 5;
export const MAX_RULES = 10;
export const MAX_DELAY_SECONDS = 23 * 3600;

// ---------------------------------------------------------------- ids

const ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789";

/** A step id the API accepts (lower case, digits, - and _), unique among ``taken``. */
export function newId(taken: ReadonlySet<string> = new Set()): string {
  for (;;) {
    const bytes = new Uint8Array(6);
    crypto.getRandomValues(bytes);
    const id = `s${[...bytes].map((byte) => ALPHABET[byte % ALPHABET.length]).join("")}`;
    if (!taken.has(id)) return id;
  }
}

export function makeStep(kind: StepKind, taken: ReadonlySet<string> = new Set()): EditorStep {
  const id = newId(taken);
  switch (kind) {
    case "send":
      return { kind, id, text: "", image_asset_id: null, buttons: [], replies: [], typed: { mode: "none" } };
    case "product":
      return { kind, id, product_id: null, variant_id: null, intro: "" };
    case "ask":
      return { kind, id, text: "", expect: "email",
        field_key: null,
        retry_text: "",
        tries: 2,
        consent: false,
        consent_text: "",
        confirm_text: "",
        skip: [],
      };
    case "branch":
      return { kind, id, rules: [{ when: { kind: "contact", has: "email", known: true }, steps: [] }], otherwise: [] };
    case "action":
      return { kind, id, action: { kind: "notify_team", note: "" } };
    case "delay":
      return { kind, id, seconds: 600 };
    case "split":
      return {
        kind,
        id,
        paths: [
          { weight: 1, steps: [] },
          { weight: 1, steps: [] },
        ],
      };
    case "ai":
      return { kind, id, instructions: "" };
    case "end":
      return { kind, id };
  }
}

// ---------------------------------------------------------------- slots: the lists inside a step

/** Names a list inside a step: "reply:0", "typed", "skip", "rule:1", "otherwise", "path:0". */
export type Slot = string;

export type Arm = { slot: Slot; label: string; steps: EditorStep[] };

/** The lists a step holds, in the order they show. A typed answer that reuses an option has none. */
export function armsOf(node: EditorStep): Arm[] {
  switch (node.kind) {
    case "send": {
      const arms: Arm[] = node.replies.map((reply, index) => ({
        slot: `reply:${index}`,
        label: reply.title.trim() ? `If they tap "${reply.title.trim()}"` : `If they tap option ${index + 1}`,
        steps: reply.steps,
      }));
      if (node.typed.mode === "own") arms.push({ slot: "typed", label: "If they type an answer", steps: node.typed.steps });
      return arms;
    }
    case "ask":
      return node.skip ? [{ slot: "skip", label: "If the answer doesn't fit", steps: node.skip }] : [];
    case "branch":
      return [
        ...node.rules.map((rule, index) => ({
          slot: `rule:${index}`,
          label: `If ${describeCondition(rule.when).toLowerCase()}`,
          steps: rule.steps,
        })),
        { slot: "otherwise", label: "Otherwise", steps: node.otherwise },
      ];
    case "split":
      return node.paths.map((path, index) => ({
        slot: `path:${index}`,
        label: `Path ${letter(index)} · weight ${path.weight}`,
        steps: path.steps,
      }));
    default:
      return [];
  }
}

export function letter(index: number): string {
  return String.fromCharCode(65 + index);
}

/** The step with one of its lists replaced. */
export function withArm(node: EditorStep, slot: Slot, steps: EditorStep[]): EditorStep {
  const [kind, raw] = slot.split(":");
  const index = Number(raw);
  switch (node.kind) {
    case "send":
      if (kind === "reply") return { ...node, replies: node.replies.map((r, i) => (i === index ? { ...r, steps } : r)) };
      if (kind === "typed" && node.typed.mode === "own") return { ...node, typed: { mode: "own", steps } };
      return node;
    case "ask":
      return kind === "skip" ? { ...node, skip: steps } : node;
    case "branch":
      if (kind === "rule") return { ...node, rules: node.rules.map((r, i) => (i === index ? { ...r, steps } : r)) };
      return kind === "otherwise" ? { ...node, otherwise: steps } : node;
    case "split":
      return kind === "path" ? { ...node, paths: node.paths.map((p, i) => (i === index ? { ...p, steps } : p)) } : node;
    default:
      return node;
  }
}

/** A list in the tree: the root (parent null) or one of a step's slots. */
export type ListRef = { parent: string | null; slot: Slot };
export const ROOT: ListRef = { parent: null, slot: "root" };

function mapNodes(list: EditorStep[], change: (node: EditorStep) => EditorStep): EditorStep[] {
  return list.map((node) => {
    let next = change(node);
    for (const arm of armsOf(next)) next = withArm(next, arm.slot, mapNodes(arm.steps, change));
    return next;
  });
}

/** Every step, depth first in the order the cards show (a step, then its lists, then the next). */
export function flatten(list: EditorStep[]): EditorStep[] {
  return list.flatMap((node) => [node, ...armsOf(node).flatMap((arm) => flatten(arm.steps))]);
}

export function countSteps(list: EditorStep[]): number {
  return flatten(list).length;
}

export function findStep(list: EditorStep[], id: string): EditorStep | undefined {
  return flatten(list).find((node) => node.id === id);
}

export function stepIds(list: EditorStep[]): Set<string> {
  return new Set(flatten(list).map((node) => node.id));
}

/** Change one step's own fields (not its lists). */
export function updateStep(list: EditorStep[], id: string, change: (node: EditorStep) => EditorStep): EditorStep[] {
  return mapNodes(list, (node) => (node.id === id ? change(node) : node));
}

/** Change one list. */
export function updateList(list: EditorStep[], ref: ListRef, change: (steps: EditorStep[]) => EditorStep[]): EditorStep[] {
  if (ref.parent === null) return change(list);
  const walk = (steps: EditorStep[]): EditorStep[] =>
    steps.map((node) => {
      let next = node;
      if (node.id === ref.parent) {
        const arm = armsOf(node).find((a) => a.slot === ref.slot);
        if (arm) next = withArm(next, ref.slot, change(arm.steps));
      }
      for (const arm of armsOf(next)) next = withArm(next, arm.slot, walk(arm.steps));
      return next;
    });
  return walk(list);
}

export function removeStep(list: EditorStep[], id: string): EditorStep[] {
  const drop = (steps: EditorStep[]): EditorStep[] =>
    steps
      .filter((node) => node.id !== id)
      .map((node) => {
        let next = node;
        for (const arm of armsOf(node)) next = withArm(next, arm.slot, drop(arm.steps));
        return next;
      });
  return drop(list);
}

/** Where a step is: its list, its index in it. */
export function locate(list: EditorStep[], id: string): { ref: ListRef; index: number; length: number } | null {
  const search = (steps: EditorStep[], ref: ListRef): { ref: ListRef; index: number; length: number } | null => {
    const index = steps.findIndex((node) => node.id === id);
    if (index >= 0) return { ref, index, length: steps.length };
    for (const node of steps) {
      for (const arm of armsOf(node)) {
        const found = search(arm.steps, { parent: node.id, slot: arm.slot });
        if (found) return found;
      }
    }
    return null;
  };
  return search(list, ROOT);
}

export function move<T>(items: T[], from: number, to: number): T[] {
  if (from === to || to < 0 || to >= items.length) return items;
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

/** Whether a step can have something after it: End and the AI reply stop the flow. */
export function endsFlow(node: EditorStep | undefined): boolean {
  return node?.kind === "end" || node?.kind === "ai";
}

/** Whether an arm's end carries on with a step below the fork (so the card can say so). */
export function hasFollower(list: EditorStep[], index: number, outerFollower: boolean): boolean {
  return index < list.length - 1 || outerFollower;
}

// ---------------------------------------------------------------- compile: tree -> graph

export type Compiled = {
  definition: FlowDefinition;
  /** The step id at each index of ``definition.steps``, to read the API's ``flow.steps.N`` paths. */
  ids: string[];
};

export function compile(tree: EditorStep[]): Compiled {
  const steps: FlowStep[] = [];
  const ids: string[] = [];

  const emit = (list: EditorStep[], after: string | null) => {
    list.forEach((node, i) => {
      const next = list[i + 1]?.id ?? after;
      const first = (arm: EditorStep[]) => arm[0]?.id ?? next;
      ids.push(node.id);
      switch (node.kind) {
        case "send": {
          const quick_replies = node.replies.map((reply) => ({ title: reply.title, next: first(reply.steps) }));
          let on_text: string | null = null;
          if (node.replies.length > 0) {
            if (node.typed.mode === "own") on_text = first(node.typed.steps);
            else if (node.typed.mode === "same") on_text = quick_replies[node.typed.index]?.next ?? null;
          }
          if (node.saved) {
            steps.push({ type: "send", id: node.id, text: "", saved_reply_id: node.saved_reply_id ?? null, next });
            break;
          }
          steps.push({
            type: "send",
            id: node.id,
            text: node.text,
            image_asset_id: node.image_asset_id,
            buttons: node.buttons,
            quick_replies,
            on_text,
            next: node.replies.length > 0 ? null : next,
          });
          break;
        }
        case "product":
          steps.push({
            type: "product",
            id: node.id,
            product_id: node.product_id ?? "",
            variant_id: node.variant_id,
            intro: node.intro,
            next,
          });
          break;
        case "ask":
          steps.push({
            type: "ask",
            id: node.id,
            text: node.text,
            expect: node.expect,
            field_key: node.field_key,
            retry_text: node.retry_text,
            tries: node.tries,
            consent: node.consent,
            consent_text: node.consent ? node.consent_text : "",
            confirm_text: node.confirm_text,
            next,
            on_skip: node.skip === null ? null : first(node.skip),
          });
          break;
        case "branch":
          steps.push({
            type: "branch",
            id: node.id,
            rules: node.rules.map((rule) => ({ when: rule.when, next: first(rule.steps) })),
            otherwise: first(node.otherwise),
          });
          break;
        case "action":
          steps.push({ type: "action", id: node.id, action: node.action, next });
          break;
        case "delay":
          steps.push({ type: "delay", id: node.id, seconds: node.seconds, next });
          break;
        case "split":
          steps.push({
            type: "randomize",
            id: node.id,
            paths: node.paths.map((path) => ({ weight: path.weight, next: first(path.steps) })),
          });
          break;
        case "ai":
          steps.push({ type: "ai_reply", id: node.id, instructions: node.instructions });
          break;
        case "end":
          steps.push({ type: "end", id: node.id });
          break;
      }
      for (const arm of armsOf(node)) emit(arm.steps, next);
    });
  };
  emit(tree, null);
  return { definition: { schema_version: 1, start: tree[0]?.id ?? "", steps }, ids };
}

// ---------------------------------------------------------------- decompile: graph -> tree

/** The ids a stored step can lead to, in order (null: the flow ends there). */
export function successors(step: FlowStep): (string | null)[] {
  switch (step.type) {
    case "send":
      return step.quick_replies?.length
        ? [...step.quick_replies.map((reply) => reply.next ?? null), step.on_text ?? null]
        : [step.next ?? null];
    case "ask":
      return [step.next ?? null, step.on_skip ?? null];
    case "branch":
      return [...(step.rules ?? []).map((rule) => rule.next ?? null), step.otherwise ?? null];
    case "randomize":
      return step.paths.map((path) => path.next ?? null);
    case "action":
    case "delay":
    case "product":
      return [step.next ?? null];
    default:
      return [];
  }
}

/** The stored flow as a tree, or null when its shape is one the editor can't show. */
export function decompile(definition: FlowDefinition): EditorStep[] | null {
  const byId = new Map(definition.steps.map((step) => [step.id, step]));
  if (byId.size !== definition.steps.length || !byId.has(definition.start)) return null;

  const reachCache = new Map<string, Set<string>>();
  const reach = (id: string): Set<string> => {
    const cached = reachCache.get(id);
    if (cached) return cached;
    const seen = new Set<string>();
    const stack = [id];
    while (stack.length > 0) {
      const current = stack.pop() as string;
      if (seen.has(current)) continue;
      seen.add(current);
      const step = byId.get(current);
      if (step) for (const target of successors(step)) if (target !== null) stack.push(target);
    }
    reachCache.set(id, seen);
    return seen;
  };

  /**
   * The step the exits come back to: the earliest step that most of them reach (at least two).
   * An exit that ends first (an End step) simply doesn't come back; null when no step is reached
   * by two exits, or when two unrelated steps tie.
   */
  const joinOf = (targets: (string | null)[]): string | null => {
    const live = targets.filter((target): target is string => target !== null);
    if (live.length < 2) return null;
    const counts = new Map<string, number>();
    for (const target of live) for (const id of reach(target)) counts.set(id, (counts.get(id) ?? 0) + 1);
    const best = Math.max(...counts.values());
    if (best < 2) return null;
    const tied = [...counts].filter(([, count]) => count === best).map(([id]) => id);
    const earliest = tied.filter((id) => !tied.some((other) => other !== id && reach(other).has(id)));
    return earliest.length === 1 ? earliest[0] : null;
  };

  const taken = new Set(byId.keys());
  const visited = new Set<string>();
  const ended = (): EditorStep => {
    const id = newId(taken);
    taken.add(id);
    return { kind: "end", id };
  };

  /** The steps from ``start`` down to ``stop`` (exclusive); null when the shape isn't a tree. */
  const chain = (start: string | null, stop: string | null): EditorStep[] | null => {
    const list: EditorStep[] = [];
    let current = start;
    while (current !== null && current !== stop) {
      if (visited.has(current)) return null;
      visited.add(current);
      const step = byId.get(current);
      if (!step) return null;
      switch (step.type) {
        case "action":
          list.push({ kind: "action", id: step.id, action: step.action });
          current = step.next ?? null;
          break;
        case "delay":
          list.push({ kind: "delay", id: step.id, seconds: step.seconds });
          current = step.next ?? null;
          break;
        case "product":
          list.push({
            kind: "product",
            id: step.id,
            product_id: step.product_id || null,
            variant_id: step.variant_id ?? null,
            intro: step.intro ?? "",
          });
          current = step.next ?? null;
          break;
        case "end":
          list.push({ kind: "end", id: step.id });
          return list;
        case "ai_reply":
          list.push({ kind: "ai", id: step.id, instructions: step.instructions ?? "" });
          return list;
        case "ask": {
          const next = step.next ?? null;
          const onSkip = step.on_skip ?? null;
          let skip: EditorStep[] | null;
          if (onSkip === null) skip = null;
          else if (onSkip === next) skip = [];
          else {
            skip = chain(onSkip, next ?? stop);
            if (skip === null) return null;
          }
          list.push({
            kind: "ask",
            id: step.id,
            text: step.text,
            expect: step.expect,
            field_key: step.field_key ?? null,
            retry_text: step.retry_text,
            tries: step.tries,
            consent: step.consent ?? false,
            consent_text: step.consent_text ?? "",
            confirm_text: step.confirm_text ?? "",
            skip,
          });
          current = next;
          break;
        }
        case "send": {
          const replies = step.quick_replies ?? [];
          const base = {
            kind: "send" as const,
            id: step.id,
            text: step.text,
            image_asset_id: step.image_asset_id ?? null,
            buttons: step.buttons ?? [],
            ...(step.saved_reply_id ? { saved: true, saved_reply_id: step.saved_reply_id } : {}),
          };
          if (replies.length === 0) {
            list.push({ ...base, replies: [], typed: { mode: "none" } });
            current = step.next ?? null;
            break;
          }
          const targets = replies.map((reply) => reply.next ?? null);
          const onText = step.on_text ?? null;
          const join = joinOf([...targets, onText]);
          const arm = (target: string | null) => armOf(target, join, stop, chain);
          const armsOfReplies: EditorStep[][] = [];
          for (const target of targets) {
            const steps = arm(target);
            if (steps === null) return null;
            armsOfReplies.push(steps);
          }
          let typed: TypedAnswer;
          if (onText === null) typed = { mode: "none" };
          else if (join !== null && onText === join) typed = { mode: "own", steps: [] };
          else if (targets.includes(onText)) typed = { mode: "same", index: targets.indexOf(onText) };
          else {
            const steps = armOf(onText, join, stop, chain);
            if (steps === null) return null;
            typed = { mode: "own", steps };
          }
          list.push({
            ...base,
            replies: replies.map((reply, index) => ({ title: reply.title, steps: armsOfReplies[index] })),
            typed,
          });
          if (join === null) return list;
          current = join;
          break;
        }
        case "branch": {
          const targets = [...(step.rules ?? []).map((rule) => rule.next ?? null), step.otherwise ?? null];
          const join = joinOf(targets);
          const arms: EditorStep[][] = [];
          for (const target of targets) {
            const steps = armOf(target, join, stop, chain);
            if (steps === null) return null;
            arms.push(steps);
          }
          list.push({
            kind: "branch",
            id: step.id,
            rules: (step.rules ?? []).map((rule, index) => ({ when: rule.when, steps: arms[index] })),
            otherwise: arms[arms.length - 1],
          });
          if (join === null) return list;
          current = join;
          break;
        }
        case "randomize": {
          const targets = step.paths.map((path) => path.next ?? null);
          const join = joinOf(targets);
          const arms: EditorStep[][] = [];
          for (const target of targets) {
            const steps = armOf(target, join, stop, chain);
            if (steps === null) return null;
            arms.push(steps);
          }
          list.push({
            kind: "split",
            id: step.id,
            paths: step.paths.map((path, index) => ({ weight: path.weight ?? 1, steps: arms[index] })),
          });
          if (join === null) return list;
          current = join;
          break;
        }
      }
    }
    // A path that runs out where the list is to carry on has to say it stops.
    if (current === null && stop !== null && !endsFlow(list[list.length - 1])) list.push(ended());
    return list;
  };

  const tree = chain(definition.start, null);
  if (tree === null || tree.length === 0) return null;
  // A step nothing leads to would be lost on the next save.
  if (visited.size !== definition.steps.length) return null;
  return tree;
}

/** One arm of a fork: its steps down to the join, or a lone End where it stops and others go on. */
function armOf(
  target: string | null,
  join: string | null,
  stop: string | null,
  chain: (start: string | null, stop: string | null) => EditorStep[] | null,
): EditorStep[] | null {
  if (target === null) return join !== null ? [{ kind: "end", id: newId() }] : [];
  if (target === join) return [];
  return chain(target, join ?? stop);
}

// ---------------------------------------------------------------- conditions and actions in words

export function describeCondition(when: FlowCondition, tagName?: (id: string) => string | undefined): string {
  switch (when.kind) {
    case "tag":
      return `${when.has ? "Has" : "Doesn't have"} the tag ${tagName?.(when.tag_id) ?? "a tag"}`;
    case "field":
      if (when.op === "equals") return `${when.key} is ${when.value ?? ""}`;
      return when.op === "unset" ? `${when.key} is empty` : `${when.key} is filled in`;
    case "contact":
      return `${when.known ? "Has" : "Has no"} ${when.has}`;
    case "follows_business":
      return when.follows ? "Follows you" : "Doesn't follow you";
    case "platform":
      return `Is on ${when.platform}`;
    case "lead_score":
      return `Lead score is ${when.at_least} or more`;
    case "lead_stage":
      return `Lead stage is ${when.stages.map((stage) => stage.replace("_", " ")).join(" or ")}`;
  }
}

export function describeAction(action: FlowAction, tagName?: (id: string) => string | undefined): string {
  switch (action.kind) {
    case "add_tag":
      return `Add the tag ${tagName?.(action.tag_id) ?? "a tag"}`;
    case "remove_tag":
      return `Remove the tag ${tagName?.(action.tag_id) ?? "a tag"}`;
    case "set_field":
      return `Set ${action.key} to ${action.value}`;
    case "notify_team":
      return "Notify the team";
    case "hand_off":
      return "Hand off to a person";
    case "assign":
      return action.mode === "member" ? "Assign to a team member" : action.mode === "nobody" ? "Remove the assignee" : "Assign to the next available member";
  }
}

export function describeDelay(seconds: number): string {
  if (seconds % 3600 === 0) {
    const hours = seconds / 3600;
    return `Wait ${hours} hour${hours === 1 ? "" : "s"}`;
  }
  const minutes = Math.max(1, Math.round(seconds / 60));
  return `Wait ${minutes} minute${minutes === 1 ? "" : "s"}`;
}

/** The short line a collapsed or previewed step carries. */
export function stepTitle(node: EditorStep, tagName?: (id: string) => string | undefined): string {
  switch (node.kind) {
    case "send":
      return node.saved ? "Saved reply" : "Message";
    case "product":
      return "Send a product";
    case "ask":
      return node.expect === "email" ? "Ask for an email" : node.expect === "phone" ? "Ask for a phone" : "Ask a question";
    case "branch":
      return "Branch";
    case "action":
      return describeAction(node.action, tagName);
    case "delay":
      return describeDelay(node.seconds);
    case "split":
      return "Split";
    case "ai":
      return "AI reply";
    case "end":
      return "End";
  }
}

// ---------------------------------------------------------------- checking a step

/** What the checks need to know about the workspace. */
export type FlowContext = {
  disclosure: string | null;
  /** Custom contact fields by key, with their type. */
  fields: { key: string; type: string }[];
  tagIds: ReadonlySet<string>;
  /** GR-21: the ids of the workspace's saved replies (undefined: not loaded, so not checked). */
  savedReplyIds?: ReadonlySet<string>;
  /** The id of a comment flow's first step, which can't be a saved reply (undefined: not a comment flow). */
  commentFirstId?: string | null;
  /** GR-29: the account's platform, which sets the text limit and what Messenger lacks (default Instagram). */
  platform?: Platform;
};

/** What a Facebook Page can't do in a flow, in the API's words (services/automations/flows.py). */
export const FACEBOOK_FLOW_COPY = {
  follows:
    "Messenger doesn't say whether someone follows your Page. Remove this branch or use another condition.",
  profileButton: "The profile button opens an Instagram profile. Give this button a link instead.",
  consent: "Facebook doesn't record marketing consent yet. Turn off the consent question.",
} as const;

/** Which field types hold which kind of answer (the same table as the API's). */
const ANSWER_TYPES: Record<AskNode["expect"], string[]> = {
  text: ["text", "number", "date", "choice"],
  email: ["email"],
  phone: ["phone"],
};

export function isHttps(value: string): boolean {
  try {
    return new URL(value.trim()).protocol === "https:";
  } catch {
    return false;
  }
}

export type StepProblems = Record<string, string>;

/**
 * The bracket tokens the flow templates leave for the user to fill (C-105). Activation refuses a
 * message that still holds one. Keep in step with PLACEHOLDERS in services/automations/templates.py;
 * only these tokens count, so other brackets in a message are fine.
 */
export const PLACEHOLDERS: Record<string, string> = { "[price]": "your price", "[code]": "your code" };
const PLACEHOLDER = new RegExp(Object.keys(PLACEHOLDERS).map((token) => token.replace(/[[\]]/g, "\\$&")).join("|"), "gi");

/** "Replace [price] with your price." for the first placeholder still in the text, else null. */
export function placeholderProblem(text: string): string | null {
  const found = text.match(PLACEHOLDER)?.[0]?.toLowerCase();
  return found ? `Replace ${found} with ${PLACEHOLDERS[found]}.` : null;
}

/**
 * Plain-words problems with one step, keyed by the field the API uses for it (``text``,
 * ``buttons.0.url``, ``quick_replies.1.title``...). The API checks the same things and more (what
 * Instagram allows along each path); its answers are merged with these.
 */
export function stepProblems(node: EditorStep, ctx: FlowContext): StepProblems {
  const out: StepProblems = {};
  const textProblems = (text: string, buttons: boolean, what: string) => {
    if (!text.trim()) out.text = `Write the ${what}.`;
    else if (placeholderProblem(text)) out.text = placeholderProblem(text) ?? "";
    else if (messageSize(text, ctx.disclosure, ctx.platform) > messageLimit(ctx.platform).limit) {
      out.text = overLimitCopy(ctx.platform, "it");
    } else if (buttons && worstCaseChars(text, ctx.disclosure) > BUTTON_TEXT_MAX_CHARS) {
      out.text = `With link buttons ${networkName(ctx.platform)} allows ${BUTTON_TEXT_MAX_CHARS} characters, counting the longest name. Shorten it.`;
    }
  };
  switch (node.kind) {
    case "send": {
      if (node.saved) {
        // A saved reply goes alone, so only the choice is checked here (the API checks its length).
        if (!node.saved_reply_id) out.saved_reply_id = "Choose a saved reply.";
        else if (ctx.savedReplyIds && !ctx.savedReplyIds.has(node.saved_reply_id)) {
          out.saved_reply_id = "That saved reply was deleted. Choose another.";
        } else if (ctx.commentFirstId === node.id) {
          out.saved_reply_id = "A reply to a comment can't be a saved reply. Write it, or use a saved reply in a later step.";
        }
        return out;
      }
      if (!node.text.trim() && !node.image_asset_id) out.text = "Write the message to send.";
      else if (node.text.trim()) textProblems(node.text, node.buttons.length > 0, "message to send");
      node.buttons.forEach((button, index) => {
        if (button.profile) {
          if (ctx.platform === "facebook") out[`buttons.${index}`] = FACEBOOK_FLOW_COPY.profileButton;
          return;
        }
        if (!button.title.trim()) out[`buttons.${index}.title`] = "Give the button a title.";
        if (!(button.url ?? "").trim()) out[`buttons.${index}.url`] = "Add a link, or make it the profile button.";
        else if (!isHttps(button.url ?? "")) out[`buttons.${index}.url`] = "Use a link that starts with https://.";
      });
      node.replies.forEach((reply, index) => {
        if (!reply.title.trim()) out[`quick_replies.${index}.title`] = "Give the option a title.";
      });
      if (node.buttons.length > 0 && node.replies.length > 0) {
        out.quick_replies = "A message can have link buttons or quick replies, not both.";
      }
      if (node.image_asset_id && node.replies.length > 0) {
        out.image_asset_id = "Quick replies go on a text message. Move the image to the step before.";
      }
      return out;
    }
    case "ask": {
      textProblems(node.text, false, "question to ask");
      for (const part of ["retry_text", "consent_text", "confirm_text"] as const) {
        if (part === "consent_text" && !node.consent) continue;
        if (placeholderProblem(node[part])) out[part] = placeholderProblem(node[part]) ?? "";
        else if (node[part].trim() && messageSize(node[part], ctx.disclosure, ctx.platform) > messageLimit(ctx.platform).limit) {
          out[part] = overLimitCopy(ctx.platform, "it", false);
        }
      }
      if (node.consent && ctx.platform === "facebook") out.consent = FACEBOOK_FLOW_COPY.consent;
      if (node.field_key === null) {
        if (node.expect === "text") out.field_key = "Choose the field to save the answer to.";
      } else {
        const field = ctx.fields.find((item) => item.key === node.field_key);
        if (!field) out.field_key = "That field doesn't exist any more. Choose another.";
        else if (!ANSWER_TYPES[node.expect].includes(field.type)) {
          out.field_key = "This field can't hold that kind of answer. Choose a field of the same type.";
        }
      }
      return out;
    }
    case "branch": {
      node.rules.forEach((rule, index) => {
        const when = rule.when;
        if (when.kind === "tag" && !ctx.tagIds.has(when.tag_id)) {
          out[`rules.${index}.when`] = "Choose a tag.";
        } else if (when.kind === "follows_business" && ctx.platform === "facebook") {
          out[`rules.${index}.when`] = FACEBOOK_FLOW_COPY.follows;
        } else if (when.kind === "field") {
          if (!ctx.fields.some((field) => field.key === when.key)) out[`rules.${index}.when`] = "Choose a field.";
          else if (when.op === "equals" && !(when.value ?? "").trim()) out[`rules.${index}.when`] = "Write the value to compare with.";
        }
      });
      return out;
    }
    case "action": {
      const action = node.action;
      if ((action.kind === "add_tag" || action.kind === "remove_tag") && !ctx.tagIds.has(action.tag_id)) {
        out.action = "Choose a tag.";
      } else if (action.kind === "set_field") {
        if (!ctx.fields.some((field) => field.key === action.key)) out.action = "Choose a field.";
        else if (!action.value.trim()) out["action.value"] = "Write the value to set.";
      }
      return out;
    }
    case "product":
      if (!node.product_id) out.product_id = "Choose a product.";
      else if (node.intro.trim() && messageSize(node.intro, ctx.disclosure, ctx.platform) > messageLimit(ctx.platform).limit) {
        out.intro = overLimitCopy(ctx.platform, "it", false);
      }
      return out;
    case "ai":
      if (!node.instructions.trim()) out.instructions = "Write the instructions for the AI.";
      return out;
    default:
      return out;
  }
}

// ---------------------------------------------------------------- the API's errors on steps

export type StepErrors = Record<string, Record<string, string>>;

/**
 * The API's field paths (``flow.steps.2.text``) on the editor's steps. ``flow.start`` and anything
 * else that isn't one step's comes back in ``general``.
 */
export function placeErrors(errors: ProblemField[], ids: string[]): { byStep: StepErrors; general: string[] } {
  const byStep: StepErrors = {};
  const general: string[] = [];
  for (const error of errors) {
    const match = /^flow\.steps\.(\d+)(?:\.(.+))?$/.exec(error.field);
    const id = match ? ids[Number(match[1])] : error.field === "flow.start" ? ids[0] : undefined;
    if (!id) {
      general.push(error.message);
      continue;
    }
    const field = match?.[2] ?? "";
    byStep[id] ??= {};
    if (!(field in byStep[id])) byStep[id][field] = error.message;
  }
  return { byStep, general };
}

/** The same fields keyed as the old message editor's, so the shared link-button editor can show them. */
export function buttonErrors(problems: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [field, message] of Object.entries(problems)) {
    if (field.startsWith("buttons.")) out[`message_buttons.${field.slice("buttons.".length)}`] = message;
  }
  return out;
}

/** An automation's settings errors (a flow compiled from them) on the compiled flow's steps. */
export function legacyErrorStep(field: string): { id: string; field: string } | null {
  const [root, ...rest] = field.split(".");
  switch (root) {
    case "message_text":
      return { id: "message", field: "text" };
    case "message_media_asset_id":
      return { id: "message", field: "image_asset_id" };
    case "message_buttons":
      return { id: "message", field: `buttons.${rest.join(".")}` };
    case "opening_text":
      return { id: "opening", field: "text" };
    case "opening_button":
      return { id: "opening", field: "quick_replies.0.title" };
    case "follow_nudge_text":
      return { id: "nudge", field: "text" };
    default:
      return null;
  }
}

// ---------------------------------------------------------------- the walk: preview and dry run

/** One step of a walk, the same shape as the API's dry run (``FlowPreviewStep``). */
export type PathStep = FlowPreviewStep;

/**
 * The steps one run would take, choosing at each fork the exit ``choices`` names (0 where none).
 * The same walk as the API's dry run, on the draft, so the Preview follows every keystroke.
 */
export function walk(
  definition: FlowDefinition,
  options: {
    choices?: number[];
    values: FieldValues;
    disclosure: string | null;
    tagName?: (id: string) => string | undefined;
    /** GR-21: a saved reply's title, shown in place of its text. */
    savedReplyTitle?: (id: string) => string | undefined;
  },
): PathStep[] {
  const byId = new Map(definition.steps.map((step) => [step.id, step]));
  const remaining = [...(options.choices ?? [])];
  const out: PathStep[] = [];
  const seen = new Set<string>();
  let current: string | null = byId.has(definition.start) ? definition.start : null;
  while (current !== null && !seen.has(current)) {
    seen.add(current);
    const step = byId.get(current);
    if (!step) break;
    const targets = successors(step);
    const forks = targets.length > 1;
    const picked = forks ? Math.min(remaining.shift() ?? 0, targets.length - 1) : null;
    const following: string | null = forks ? targets[picked as number] : (targets[0] ?? null);
    const savedTitle = step.type === "send" && step.saved_reply_id ? options.savedReplyTitle?.(step.saved_reply_id) : undefined;
    const text =
      step.type === "send" && step.saved_reply_id
        ? `Saved reply: ${savedTitle ?? "(not found)"}`
        : (step.type === "send" || step.type === "ask") && step.text.trim()
          ? withDisclosure(renderFields(step.text, options.values), options.disclosure)
          : null;
    out.push({
      step_id: step.id,
      kind: step.type,
      title: wireTitle(step, options.tagName),
      text,
      buttons: step.type === "send" ? (step.buttons ?? []).map((button) => button.title) : [],
      quick_replies: step.type === "send" ? (step.quick_replies ?? []).map((reply) => reply.title) : [],
      exits: forks ? exitLabels(step, options.tagName) : [],
      picked,
    });
    current = following;
  }
  return out;
}

function wireTitle(step: FlowStep, tagName?: (id: string) => string | undefined): string {
  switch (step.type) {
    case "send":
      return step.saved_reply_id ? "Saved reply" : "Message";
    case "product":
      return "Send a product";
    case "ask":
      return step.expect === "email" ? "Ask for an email" : step.expect === "phone" ? "Ask for a phone" : "Ask a question";
    case "branch":
      return "Branch";
    case "action":
      return describeAction(step.action, tagName);
    case "delay":
      return describeDelay(step.seconds);
    case "randomize":
      return "Split";
    case "ai_reply":
      return "AI reply";
    case "end":
      return "End";
  }
}

function exitLabels(step: FlowStep, tagName?: (id: string) => string | undefined): string[] {
  switch (step.type) {
    case "send":
      return [...(step.quick_replies ?? []).map((reply) => `Taps ${reply.title}`), "Types an answer"];
    case "ask":
      return ["Answers", "Doesn't answer in a way that fits"];
    case "branch":
      return [...(step.rules ?? []).map((rule) => describeCondition(rule.when, tagName)), "Otherwise"];
    case "randomize":
      return step.paths.map((path, index) => `Path ${letter(index)} (${path.weight ?? 1})`);
    default:
      return [];
  }
}

// ---------------------------------------------------------------- reordering by pointer

/**
 * Where a dragged card would land: the index among the other cards, given each card's vertical
 * middle (top to bottom, the dragged card excluded) and the pointer's y.
 */
export function dropIndex(middles: number[], pointerY: number): number {
  let index = 0;
  for (const middle of middles) if (pointerY > middle) index += 1;
  return index;
}

/** Whether every step is filled in (the editor's checks; the API's path checks come on activation). */
export function flowComplete(tree: EditorStep[], ctx: FlowContext): boolean {
  return flatten(tree).every((node) => Object.keys(stepProblems(node, ctx)).length === 0);
}
