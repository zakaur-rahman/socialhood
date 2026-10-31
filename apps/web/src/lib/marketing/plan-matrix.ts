/**
 * The pricing page's comparison table (GR-37): every plan limit in billing/plans.py, grouped and
 * worded for a visitor. The numbers are never typed here. They come from plan-table.json, which is
 * exported from the API's ENTITLEMENTS and checked against it by tests/unit/test_marketing_plan_table.py,
 * and plan-matrix.test.ts checks that every entitlement in the file has a row below (or is left out
 * on purpose), so a new limit can't ship without the page deciding how to say it.
 *
 * Prices are not here: they come from Dodo through GET /v1/billing/plans (lib/marketing/plans.ts).
 * Values the owner has not confirmed (catalogue and sequence caps, C-116 and C-118) are shown as
 * they are in the code today and may change.
 */
import table from "./plan-table.json";

export type PlanKey = "free" | "pro" | "max";
export const MATRIX_PLANS: PlanKey[] = ["free", "pro", "max"];

export type EntitlementKey = keyof typeof table.entitlements;
type Raw = number | boolean | string[] | null;

/** How a raw value reads in a cell. */
type Kind =
  | { kind: "count"; unit?: string }
  | { kind: "flag" }
  | { kind: "modes" }
  | { kind: "days" }
  /** 0 is "Not included"; any other number is a count. */
  | { kind: "quota"; unit?: string };

export type MatrixRow = {
  key: EntitlementKey;
  label: string;
  format: Kind;
  /** One line under the label, for a limit with a condition a visitor should know. */
  note?: string;
};

export type MatrixGroup = { id: string; title: string; rows: MatrixRow[] };

export const MATRIX: MatrixGroup[] = [
  {
    id: "accounts",
    title: "Accounts and team",
    rows: [
      { key: "accounts_per_platform", label: "Accounts per platform", format: { kind: "count" }, note: "Instagram, WhatsApp and Facebook Pages each count on their own." },
      { key: "members", label: "Team members", format: { kind: "count" }, note: "The owner and any pending invitation count." },
      { key: "message_history_days", label: "Message history", format: { kind: "days" } },
    ],
  },
  {
    id: "ai",
    title: "AI",
    rows: [
      { key: "ai_credits_monthly", label: "AI credits a month", format: { kind: "count" } },
      { key: "ai_modes", label: "AI reply modes", format: { kind: "modes" } },
      { key: "ai_reply_automations", label: "AI replies inside automations", format: { kind: "flag" } },
      { key: "knowledge_characters", label: "Characters of knowledge", format: { kind: "count" } },
      { key: "crawl_pages", label: "Pages read in one website crawl", format: { kind: "count" } },
      { key: "comment_intelligence_posts", label: "Posts with comment analysis, per account", format: { kind: "count", unit: "latest" } },
    ],
  },
  {
    id: "automation",
    title: "Automations",
    rows: [
      { key: "active_automations", label: "Active automations", format: { kind: "count" } },
      { key: "flow_steps", label: "Steps in one flow", format: { kind: "count" } },
      { key: "active_sequences", label: "Active sequences", format: { kind: "count" }, note: "Template steps are messages Meta bills your business for." },
      { key: "sequence_steps", label: "Steps in one sequence", format: { kind: "count" } },
      { key: "pending_scheduled_messages", label: "Pending scheduled messages", format: { kind: "count" } },
      { key: "contact_fields", label: "Custom contact fields", format: { kind: "count" } },
    ],
  },
  {
    id: "whatsapp",
    title: "WhatsApp and products",
    rows: [
      {
        key: "broadcast_recipients_monthly",
        label: "WhatsApp broadcast recipients a month",
        format: { kind: "quota" },
        note: "Coming soon: broadcasts open after our review of consent rules. Meta bills the messages to your business.",
      },
      { key: "commerce", label: "Product catalogue", format: { kind: "flag" }, note: "Shopify sync arrives with our Shopify app listing." },
      { key: "catalogue_products", label: "Products in the catalogue", format: { kind: "quota" } },
      { key: "orders_monthly", label: "Orders a month", format: { kind: "quota" }, note: "Orders you create from a chat, with a Razorpay link or UPI payment request." },
      { key: "catalogue_import_rows", label: "Rows in one CSV import", format: { kind: "quota" } },
    ],
  },
  {
    id: "publishing",
    title: "Publishing and website chat",
    rows: [
      { key: "scheduled_posts_monthly", label: "Scheduled posts a month", format: { kind: "count" } },
      { key: "widget_conversations_daily", label: "New website chats a day", format: { kind: "count" } },
      { key: "widget_remove_branding", label: "Remove Powered by Amplychat", format: { kind: "flag" } },
    ],
  },
  {
    id: "developers",
    title: "Integrations and developers",
    rows: [
      { key: "webhook_endpoints", label: "Outbound webhook endpoints", format: { kind: "count" } },
      { key: "public_api", label: "Public API, API keys and the Zapier app", format: { kind: "flag" } },
      { key: "sheets_sync", label: "Google Sheets sync", format: { kind: "flag" } },
    ],
  },
];

const number = new Intl.NumberFormat("en-US");

/** One cell: the entitlement's value for a plan, in words. */
export function cellText(row: MatrixRow, plan: PlanKey): string {
  const value = (table.entitlements[row.key] as unknown as Record<PlanKey, Raw>)[plan];
  const { format } = row;
  switch (format.kind) {
    case "flag":
      return value === true ? "Included" : "Not included";
    case "modes":
      return Array.isArray(value) ? value.map((mode) => mode.charAt(0).toUpperCase() + mode.slice(1)).join(", ") : "Not included";
    case "days":
      return value === null ? "Unlimited" : typeof value === "number" ? `${number.format(value)} days` : "Not included";
    case "quota":
      if (value === 0) return "Not included";
      return value === null ? "Unlimited" : typeof value === "number" ? number.format(value) : "Not included";
    case "count":
      if (value === null) return "Unlimited";
      if (typeof value !== "number") return "Not included";
      return format.unit === "latest" ? `Latest ${number.format(value)}` : number.format(value);
  }
}

/** Comment analysis is "all posts" when unlimited, which reads better than "Unlimited". */
export function rowCell(row: MatrixRow, plan: PlanKey): string {
  if (row.key === "comment_intelligence_posts" && cellText(row, plan) === "Unlimited") return "All posts";
  return cellText(row, plan);
}

/** Entitlements the table leaves out on purpose. C-165: what AI apps may do and their daily tool
 * calls are explained on /developers/mcp (its plans table), not in the pricing table. */
export const NOT_SHOWN: EntitlementKey[] = ["ai_connections", "mcp_calls_daily"];

export const PLAN_TABLE_KEYS = Object.keys(table.entitlements) as EntitlementKey[];
export const TRIAL_DAYS = table.trial_days;
