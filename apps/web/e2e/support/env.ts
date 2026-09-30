import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Where the e2e stack runs (scripts/e2e-stack.mjs). The launcher passes these in the environment;
 * with `--serve` it writes them to e2e/.stack.json so `playwright test` can run on its own.
 */
type StackValues = {
  E2E_BASE_URL: string;
  E2E_API_URL: string;
  E2E_SEED_TOKEN: string;
  E2E_DODO_WEBHOOK_SECRET: string;
  E2E_DODO_PRO_PRODUCT: string;
};

const STACK_FILE = join(__dirname, "..", ".stack.json");

function load(): StackValues | null {
  if (process.env.E2E_BASE_URL && process.env.E2E_API_URL && process.env.E2E_SEED_TOKEN) {
    return {
      E2E_BASE_URL: process.env.E2E_BASE_URL,
      E2E_API_URL: process.env.E2E_API_URL,
      E2E_SEED_TOKEN: process.env.E2E_SEED_TOKEN,
      E2E_DODO_WEBHOOK_SECRET: process.env.E2E_DODO_WEBHOOK_SECRET ?? "",
      E2E_DODO_PRO_PRODUCT: process.env.E2E_DODO_PRO_PRODUCT ?? "",
    };
  }
  if (existsSync(STACK_FILE)) return JSON.parse(readFileSync(STACK_FILE, "utf8")) as StackValues;
  return null;
}

const values = load();

/** Null when the stack isn't running; global setup explains how to start it. */
export const stack = values;

export function requireStack(): StackValues {
  if (!values) {
    throw new Error(
      "The e2e stack isn't running. Run `pnpm e2e` from the repository root (or " +
        "`node scripts/e2e-stack.mjs --serve` and then `pnpm exec playwright test` in apps/web).",
    );
  }
  return values;
}

export const BASE_URL = values?.E2E_BASE_URL ?? "http://localhost:3100";

/** The dedicated test user on the Clerk development instance (created by global setup). */
export const E2E_USER = {
  email: "socialhood-e2e+clerk_test@example.com",
  firstName: "Esme",
  lastName: "Tester",
};

/** Users that F-01 signs up; global setup and teardown delete any left behind. */
export const SIGN_UP_EMAIL_PREFIX = "socialhood-e2e-signup-";

export const AUTH_FILE = join(__dirname, "..", ".auth", "user.json");
