import type { Sequence } from "@/lib/api/types";

/** A sequence as the API returns it, for the sequence tests (GR-24). */
export function sequence(values: Partial<Sequence> = {}): Sequence {
  return {
    id: "s1",
    name: "Welcome follow-up",
    status: "active",
    social_account_id: "wa1",
    account_label: "Maple Orders",
    platform: "whatsapp",
    entry: { type: "tagged", tag_id: "t1", tag_name: "Follow up", label: "A tag is added: Follow up" },
    stop: { on_reply: true, tag_ids: [], tag_names: [], stages: [] },
    allow_reentry: false,
    step_count: 3,
    enrolments: { active: 4, completed: 2, stopped: 1 },
    activated_at: "2026-10-25T09:00:00Z",
    created_at: "2026-10-25T08:00:00Z",
    updated_at: "2026-10-25T09:00:00Z",
    problems: [],
    ...values,
  } as Sequence;
}
