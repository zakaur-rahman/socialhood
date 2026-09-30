import type { PlanOfferBody } from "@/lib/marketing/plans";

/**
 * GET /v1/billing/plans as the API answers it (billing/plans.py, C-049), with Pro priced by Dodo
 * in rupees. Tests change the price or availability per case.
 */
export function plansFixture(overrides: { proPrice?: PlanOfferBody["price"] } = {}): { items: PlanOfferBody[] } {
  return {
    items: [
      {
        plan: "free",
        price: null,
        trial_days: 0,
        available: true,
        entitlements: [
          { key: "accounts_per_platform", value: 1 },
          { key: "members", value: 1 },
          { key: "active_automations", value: 3 },
          { key: "ai_reply_automations", value: false },
          { key: "ai_modes", value: ["off", "suggest"] },
          { key: "ai_credits_monthly", value: 200 },
          { key: "knowledge_characters", value: 200_000 },
          { key: "scheduled_posts_monthly", value: 10 },
          { key: "pending_scheduled_messages", value: 20 },
          { key: "message_history_days", value: 90 },
          { key: "comment_intelligence_posts", value: 5 },
        ],
      },
      {
        plan: "pro",
        price: "proPrice" in overrides ? overrides.proPrice : { amount_minor: 99_900, currency: "INR", interval: "month" },
        trial_days: 7,
        available: true,
        entitlements: [
          { key: "accounts_per_platform", value: 3 },
          { key: "members", value: 1 },
          { key: "active_automations", value: 50 },
          { key: "ai_reply_automations", value: true },
          { key: "ai_modes", value: ["off", "suggest", "auto"] },
          { key: "ai_credits_monthly", value: 5000 },
          { key: "knowledge_characters", value: 5_000_000 },
          { key: "scheduled_posts_monthly", value: 300 },
          { key: "pending_scheduled_messages", value: 500 },
          { key: "message_history_days", value: null },
          { key: "comment_intelligence_posts", value: null },
        ],
      },
      {
        plan: "max",
        price: null,
        trial_days: 0,
        available: false,
        entitlements: [
          { key: "accounts_per_platform", value: 10 },
          { key: "members", value: 10 },
          { key: "active_automations", value: null },
          { key: "ai_reply_automations", value: true },
          { key: "ai_modes", value: ["off", "suggest", "auto"] },
          { key: "ai_credits_monthly", value: 25_000 },
          { key: "knowledge_characters", value: 50_000_000 },
          { key: "scheduled_posts_monthly", value: null },
          { key: "pending_scheduled_messages", value: null },
          { key: "message_history_days", value: null },
          { key: "comment_intelligence_posts", value: null },
        ],
      },
    ],
  };
}

/** A fetch that answers the plan list with this body (and status). */
export function plansFetch(body: unknown, status = 200) {
  return async () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
