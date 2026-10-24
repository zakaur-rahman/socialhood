import type {
  EnrolmentStatus,
  Sequence,
  SequenceBody,
  SequenceEntryType,
  SequenceStatus,
  VariableSpec,
  WhatsAppTemplate,
} from "@/lib/api/types";
import type { Tone } from "@/lib/ui/tone";

/** A sequence's status in words and tone (GR-24). Colour never stands alone: the badge says it. */
export const SEQUENCE_STATUS: Record<SequenceStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  active: { label: "On", tone: "success" },
  paused: { label: "Paused", tone: "warning" },
};

export const ENROLMENT_STATUS: Record<EnrolmentStatus, { label: string; tone: Tone }> = {
  active: { label: "In it", tone: "brand" },
  completed: { label: "Finished", tone: "success" },
  stopped: { label: "Stopped", tone: "warning" },
};

export const ENTRY_TYPES: { value: SequenceEntryType; label: string }[] = [
  { value: "captured", label: "A lead is captured" },
  { value: "tagged", label: "A tag is added" },
  { value: "broadcast_replied", label: "Someone replies to a broadcast" },
];

export const CAPTURE_KINDS: { value: "any" | "email" | "phone" | "field"; label: string }[] = [
  { value: "any", label: "Anything they answer" },
  { value: "email", label: "An email" },
  { value: "phone", label: "A phone number" },
  { value: "field", label: "A question saved to a field" },
];

export const STOP_STAGES: { value: string; label: string }[] = [
  { value: "qualified", label: "Qualified" },
  { value: "follow_up", label: "Follow up" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

export type Unit = "minutes" | "hours" | "days";
export const UNIT_SECONDS: Record<Unit, number> = { minutes: 60, hours: 3600, days: 86_400 };
export const MAX_DELAY_DAYS = 30;

/** A delay in the largest unit that divides it evenly (0 is "0 minutes"). */
export function splitDelay(seconds: number): { amount: number; unit: Unit } {
  if (seconds > 0 && seconds % UNIT_SECONDS.days === 0) return { amount: seconds / UNIT_SECONDS.days, unit: "days" };
  if (seconds > 0 && seconds % UNIT_SECONDS.hours === 0) return { amount: seconds / UNIT_SECONDS.hours, unit: "hours" };
  return { amount: Math.round(seconds / UNIT_SECONDS.minutes), unit: "minutes" };
}

export function toSeconds(amount: number, unit: Unit): number {
  const seconds = Math.round(amount) * UNIT_SECONDS[unit];
  return Math.max(0, Math.min(MAX_DELAY_DAYS * UNIT_SECONDS.days, seconds));
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** "1 day", "90 minutes", "2 hours". */
export function formatDelay(seconds: number): string {
  const { amount, unit } = splitDelay(seconds);
  return plural(amount, unit.slice(0, -1));
}

/** Where a step's wait is counted from, in words: "1 day after they entered". */
export function describeWait(seconds: number, from: "entry" | "previous", position: number): string {
  if (seconds === 0) return position === 0 ? "Right away" : "Right after the step before";
  const wait = formatDelay(seconds);
  return from === "entry" || position === 0 ? `${wait} after they entered` : `${wait} after the step before`;
}

/** How far after entry a preview step is: "10 min", "2 h", "Day 3" (whole days). */
export function dayOf(afterSeconds: number): string {
  if (afterSeconds < UNIT_SECONDS.hours) return `${Math.round(afterSeconds / 60)} min`;
  if (afterSeconds < UNIT_SECONDS.days) return `${Math.round(afterSeconds / 3600)} h`;
  return `Day ${Math.floor(afterSeconds / UNIT_SECONDS.days)}`;
}

// ---- the editor's state

export type VariableState = { source: "field" | "fixed"; field: string; value: string; fallback: string };

export type StepState = {
  key: string;
  amount: number;
  unit: Unit;
  from: "entry" | "previous";
  text: string;
  templateKey: string | null;
  variables: VariableState[];
  respectHours: boolean;
};

export type EditorState = {
  name: string;
  accountId: string | null;
  entryType: SequenceEntryType;
  tagId: string | null;
  broadcastId: string | null;
  captureKind: "any" | "email" | "phone" | "field";
  stopOnReply: boolean;
  stopTagIds: string[];
  stopStages: string[];
  allowReentry: boolean;
  steps: StepState[];
};

let counter = 0;
/** A stable key for a step row, so reordering keeps each row's inputs. */
export function stepKey(): string {
  counter += 1;
  return `step-${counter}`;
}

export function blankStep(over: Partial<StepState> = {}): StepState {
  return {
    key: stepKey(),
    amount: 1,
    unit: "days",
    from: "previous",
    text: "",
    templateKey: null,
    variables: [],
    respectHours: false,
    ...over,
  };
}

export function blankState(accountId: string | null = null): EditorState {
  return {
    name: "",
    accountId,
    entryType: "tagged",
    tagId: null,
    broadcastId: null,
    captureKind: "any",
    stopOnReply: true,
    stopTagIds: [],
    stopStages: [],
    allowReentry: false,
    steps: [blankStep({ amount: 1, unit: "days", from: "entry" })],
  };
}

export const templateKeyOf = (t: Pick<WhatsAppTemplate, "name" | "language">): string => `${t.name}|${t.language}`;

/** The editor's state for a saved sequence. */
export function fromSequence(sequence: Sequence): EditorState {
  return {
    name: sequence.name,
    accountId: sequence.social_account_id,
    entryType: sequence.entry.type,
    tagId: sequence.entry.tag_id ?? null,
    broadcastId: sequence.entry.broadcast_id ?? null,
    captureKind: sequence.entry.capture_kind ?? "any",
    stopOnReply: sequence.stop.on_reply,
    stopTagIds: [...sequence.stop.tag_ids],
    stopStages: [...sequence.stop.stages],
    allowReentry: sequence.allow_reentry,
    steps: (sequence.steps ?? []).map((step) => {
      const { amount, unit } = splitDelay(step.delay_seconds);
      return blankStep({
        amount,
        unit,
        from: step.delay_from,
        text: step.text ?? "",
        templateKey:
          step.template_name && step.template_language ? `${step.template_name}|${step.template_language}` : null,
        variables: (step.variables ?? []).map((v) => ({
          source: v.source,
          field: v.field ?? "first_name",
          value: v.value ?? "",
          fallback: v.fallback ?? "",
        })),
        respectHours: step.respect_hours,
      });
    }),
  };
}

function specsOf(variables: VariableState[]): VariableSpec[] {
  return variables.map((v) =>
    v.source === "fixed"
      ? { source: "fixed", value: v.value }
      : { source: "field", field: v.field, fallback: v.fallback.trim() || null },
  );
}

/** What is still missing before the sequence can be saved, in plain words (empty: ready). */
export function missingFor(state: EditorState): string[] {
  const found: string[] = [];
  if (state.name.trim() === "") found.push("Give the sequence a name.");
  if (state.accountId === null) found.push("Choose the account it sends from.");
  if (state.entryType === "tagged" && state.tagId === null) found.push("Choose the tag that starts it.");
  state.steps.forEach((step, i) => {
    const where = `Step ${i + 1}`;
    if (step.text.trim() === "" && step.templateKey === null) found.push(`${where} needs a message or a template.`);
    const incomplete = step.variables.some((v) => (v.source === "fixed" ? v.value.trim() === "" : v.field === ""));
    if (incomplete) found.push(`${where} has a template variable with nothing in it.`);
  });
  return found;
}

/** The body the API takes, or null while something is missing. */
export function toBody(state: EditorState): SequenceBody | null {
  if (missingFor(state).length > 0 || state.accountId === null) return null;
  return {
    name: state.name.trim(),
    social_account_id: state.accountId,
    entry: {
      type: state.entryType,
      tag_id: state.entryType === "tagged" ? state.tagId : null,
      broadcast_id: state.entryType === "broadcast_replied" ? state.broadcastId : null,
      capture_kind: state.entryType === "captured" && state.captureKind !== "any" ? state.captureKind : null,
    },
    stop: {
      on_reply: state.stopOnReply,
      tag_ids: state.stopTagIds,
      stages: state.stopStages as NonNullable<SequenceBody["stop"]>["stages"],
    },
    allow_reentry: state.allowReentry,
    steps: state.steps.map((step, i) => {
      const [templateName, templateLanguage] = step.templateKey ? step.templateKey.split("|") : [null, null];
      return {
        delay_seconds: toSeconds(step.amount, step.unit),
        delay_from: i === 0 ? "entry" : step.from,
        text: step.text.trim() || null,
        template_name: templateName,
        template_language: templateLanguage,
        variables: templateName ? specsOf(step.variables) : [],
        respect_hours: step.respectHours,
      };
    }),
  };
}
