// The end-to-end stack (T9.4, TR-TEST-01): starts the API (port 8100), the job worker and the
// web app (port 3100) against their own database and Valkey db, runs Playwright
// (apps/web/e2e), then stops everything and drops the database.
//
//   node scripts/e2e-stack.mjs [--skip-build] [--keep-db] [--] [playwright args, e.g. --grep F-06]
//   node scripts/e2e-stack.mjs --serve [--skip-build]
//       start the stack and keep it up (Ctrl-C stops it); meanwhile run
//       `pnpm exec playwright test` in apps/web, which finds it through apps/web/e2e/.stack.json
//
// Everything runs on fakes: the sandbox platform (TR-PL-07) instead of Meta, AI_PROVIDER=fake,
// DODO_PROVIDER=fake, EMAIL_PROVIDER=fake and PUSH_PROVIDER=fake. Only Clerk is real: its
// development instance, with testing tokens so sign-in skips bot protection. The Clerk keys come
// from the environment (CI secrets) or, locally, from apps/web/.env.local and apps/api/.env; the
// issuer and the JWT verification key are derived from the publishable key. No other value is
// read from those files, and the API and worker run where no .env file is loaded, so a local run
// and a CI run see the same configuration. Secrets are never printed.
//
// It never touches the development stack (ports 8000 and 3000, database socialhood, Valkey db 0):
// the database must be socialhood_test_<n> or socialhood_e2e* (apps/api/scripts/e2e/db.py
// refuses anything else), and the ports must be free.
import { spawn, spawnSync } from "node:child_process";
import { createPublicKey, randomBytes } from "node:crypto";
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { createConnection } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = join(root, "apps", "api");
const webDir = join(root, "apps", "web");
const e2ePy = join(apiDir, "scripts", "e2e");
const logDir = join(webDir, "e2e", "logs");
const stackFile = join(webDir, "e2e", ".stack.json");
const isWindows = process.platform === "win32";

const API_PORT = Number(process.env.E2E_API_PORT ?? 8100);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3100);
const PG = process.env.E2E_PG ?? "postgresql://socialhood:socialhood@127.0.0.1:5432";
const DB_NAME = process.env.E2E_DB_NAME ?? "socialhood_test_6";
const REDIS_URL = process.env.E2E_REDIS_URL ?? "redis://127.0.0.1:6379/5";

const FLAGS = new Set(["--skip-build", "--keep-db", "--serve", "--"]);
const args = process.argv.slice(2);
const skipBuild = args.includes("--skip-build");
const keepDb = args.includes("--keep-db");
const serve = args.includes("--serve");
const playwrightArgs = args.filter((a) => !FLAGS.has(a));

const children = [];
let stopping = false;

class StackError extends Error {}

function log(message) {
  console.log(`[e2e] ${message}`);
}

function fail(message) {
  throw new StackError(message);
}

// ---------------------------------------------------------------- configuration

function readEnvFile(path) {
  if (!existsSync(path)) return {};
  const values = {};
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const match = /^([A-Z0-9_]+)=(.*)$/.exec(line);
    if (match) values[match[1]] = match[2].trim().replace(/^"(.*)"$/, "$1");
  }
  return values;
}

function clerkKeys() {
  const web = readEnvFile(join(webDir, ".env.local"));
  const api = readEnvFile(join(apiDir, ".env"));
  const publishable =
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
    process.env.CLERK_PUBLISHABLE_KEY ||
    web.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const secret = process.env.CLERK_SECRET_KEY || api.CLERK_SECRET_KEY || web.CLERK_SECRET_KEY;
  if (!publishable || !secret) {
    fail(
      "Clerk keys are missing. Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY " +
        "(a development instance), or put them in apps/web/.env.local and apps/api/.env.",
    );
  }
  if (!publishable.startsWith("pk_test_") || !secret.startsWith("sk_test_")) {
    fail("The e2e suite only runs against a Clerk development instance (pk_test_ and sk_test_ keys).");
  }
  const frontendApi = Buffer.from(publishable.slice("pk_test_".length), "base64")
    .toString("utf8")
    .replace(/\$$/, "");
  if (!/^[a-z0-9.-]+$/i.test(frontendApi)) fail("The Clerk publishable key doesn't decode to a Frontend API host.");
  return { publishable, secret, frontendApi, issuer: process.env.CLERK_ISSUER || `https://${frontendApi}` };
}

async function clerkJwtKey(frontendApi) {
  // The instance's public key, as the API wants it (PEM), from the Frontend API's JWKS.
  const response = await fetch(`https://${frontendApi}/.well-known/jwks.json`);
  if (!response.ok) fail(`Couldn't read Clerk's JWKS (HTTP ${response.status}).`);
  const { keys } = await response.json();
  const jwk = (keys ?? []).find((k) => k.kty === "RSA");
  if (!jwk) fail("Clerk's JWKS has no RSA key.");
  return createPublicKey({ key: jwk, format: "jwk" }).export({ type: "spki", format: "pem" }).toString();
}

function python() {
  const venv = isWindows ? join(apiDir, ".venv", "Scripts", "python.exe") : join(apiDir, ".venv", "bin", "python");
  if (!existsSync(venv)) {
    log("apps/api/.venv is missing; running uv sync");
    const uv = process.env.UV ?? "uv";
    const result = spawnSync(uv, ["sync", "--locked"], { cwd: apiDir, stdio: "inherit" });
    if (result.status !== 0 || !existsSync(venv)) fail("uv sync failed; install uv or set UV to its path.");
  }
  return venv;
}

function fernetKey() {
  return randomBytes(32).toString("base64").replaceAll("+", "-").replaceAll("/", "_");
}

// ---------------------------------------------------------------- processes

function portInUse(port) {
  return new Promise((resolve) => {
    const socket = createConnection({ host: "127.0.0.1", port });
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("error", () => resolve(false));
  });
}

function run(name, command, commandArgs, options) {
  log(`${name}…`);
  const out = openSync(join(logDir, `${name}.log`), "w");
  const result = spawnSync(command, commandArgs, { ...options, stdio: ["ignore", out, out] });
  closeSync(out);
  if (result.status !== 0) fail(`${name} failed (exit ${result.status}); see apps/web/e2e/logs/${name}.log`);
}

function start(name, command, commandArgs, options) {
  const out = openSync(join(logDir, `${name}.log`), "w");
  const child = spawn(command, commandArgs, {
    ...options,
    stdio: ["ignore", out, out],
    detached: !isWindows, // its own process group, so stopping it reaches its children
  });
  child.label = name;
  child.on("exit", (code) => {
    closeSync(out);
    if (!stopping) console.error(`[e2e] ${name} exited (code ${code}); see apps/web/e2e/logs/${name}.log`);
  });
  children.push(child);
  return child;
}

function stop(child, signal = "SIGTERM") {
  if (child.exitCode !== null || child.signalCode !== null) return;
  if (isWindows) {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    return;
  }
  try {
    process.kill(-child.pid, signal);
  } catch {
    // already gone
  }
}

async function waitFor(name, url, child, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) fail(`${name} stopped while starting; see apps/web/e2e/logs/${child.label}.log`);
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // not listening yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  fail(`${name} wasn't ready after ${timeoutMs / 1000} s; see apps/web/e2e/logs/${child.label}.log`);
}

async function waitForLog(name, child, pattern, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) fail(`${name} stopped while starting; see apps/web/e2e/logs/${child.label}.log`);
    if (pattern.test(readFileSync(join(logDir, `${child.label}.log`), "utf8"))) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  fail(`${name} didn't start within ${timeoutMs / 1000} s; see apps/web/e2e/logs/${child.label}.log`);
}

async function startReady(name, command, commandArgs, options, ready) {
  for (let attempt = 1; ; attempt += 1) {
    const child = start(name, command, commandArgs, options);
    try {
      await ready(child);
      return child;
    } catch (error) {
      if (attempt >= 2 || !(error instanceof StackError)) throw error;
      log(`${error.message}; trying once more`);
      stop(child, "SIGKILL");
      children.splice(children.indexOf(child), 1);
      await new Promise((r) => setTimeout(r, 2000));
      try {
        renameSync(join(logDir, `${name}.log`), join(logDir, `${name}.first-try.log`));
      } catch {
        // still open; the retry's log replaces it
      }
    }
  }
}

// ---------------------------------------------------------------- main

async function main() {
  const started = Date.now();
  mkdirSync(logDir, { recursive: true });
  for (const port of [API_PORT, WEB_PORT]) {
    if (await portInUse(port)) fail(`Port ${port} is in use. Stop whatever runs there (the e2e stack never reuses it).`);
  }

  const clerk = clerkKeys();
  const jwtKey = await clerkJwtKey(clerk.frontendApi);
  const py = python();
  const apiUrl = `http://localhost:${API_PORT}`;
  const webUrl = `http://localhost:${WEB_PORT}`;

  const apiEnv = {
    ...process.env,
    APP_ENV: "test",
    LOG_LEVEL: "INFO",
    API_BASE_URL: apiUrl,
    WEB_BASE_URL: webUrl,
    CORS_ALLOWED_ORIGINS: webUrl,
    DATABASE_URL: `${PG.replace(/^postgresql:/, "postgresql+asyncpg:")}/${DB_NAME}`,
    DATABASE_URL_DIRECT: `${PG}/${DB_NAME}`,
    REDIS_URL,
    CLERK_SECRET_KEY: clerk.secret,
    CLERK_JWT_KEY: jwtKey,
    CLERK_ISSUER: clerk.issuer,
    CLERK_AUTHORIZED_PARTIES: webUrl,
    TOKEN_ENCRYPTION_KEYS: fernetKey(),
    SANDBOX_PLATFORM_ENABLED: "true",
    // Every test signs in as the one e2e user, from 3 workers at once: together they pass the
    // per-user 300 a minute (TR-API-07), which tests/integration/test_rate_limits.py covers.
    RATE_LIMITS_ENABLED: "false",
    AI_PROVIDER: "fake",
    DODO_PROVIDER: "fake",
    DODO_WEBHOOK_SECRET: `whsec_${randomBytes(24).toString("base64")}`,
    DODO_PRODUCT_PRO_MONTHLY: "prod_e2e_pro",
    DODO_PRODUCT_MAX_MONTHLY: "prod_e2e_max",
    EMAIL_PROVIDER: "fake",
    PUSH_PROVIDER: "fake",
    E2E_SEED_TOKEN: randomBytes(24).toString("hex"),
    PYTHONUNBUFFERED: "1",
    PYTHONIOENCODING: "utf-8",
  };
  const webEnv = {
    ...process.env,
    NEXT_PUBLIC_API_BASE_URL: apiUrl,
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: clerk.publishable,
    CLERK_SECRET_KEY: clerk.secret,
    NEXT_PUBLIC_CLERK_SIGN_IN_URL: "/sign-in",
    NEXT_PUBLIC_CLERK_SIGN_UP_URL: "/sign-up",
    NEXT_TELEMETRY_DISABLED: "1",
    CLERK_TELEMETRY_DISABLED: "1",
    NEXT_PUBLIC_CLERK_TELEMETRY_DISABLED: "1",
  };
  // What the suite needs to reach the stack (apps/web/e2e/support/env.ts reads these).
  const stack = {
    E2E_BASE_URL: webUrl,
    E2E_API_URL: `http://127.0.0.1:${API_PORT}`,
    E2E_SEED_TOKEN: apiEnv.E2E_SEED_TOKEN,
    E2E_DODO_WEBHOOK_SECRET: apiEnv.DODO_WEBHOOK_SECRET,
    E2E_DODO_PRO_PRODUCT: apiEnv.DODO_PRODUCT_PRO_MONTHLY,
  };

  // 1. A fresh database and Valkey db, migrated.
  run("db-reset", py, [join(e2ePy, "db.py"), "reset"], { cwd: e2ePy, env: apiEnv });
  run("migrate", py, ["-m", "alembic", "upgrade", "head"], { cwd: apiDir, env: apiEnv });

  // 2. The web build (NEXT_PUBLIC_* values are baked in). --skip-build reuses only a build this
  // launcher made for the same API and Clerk instance, never a development build (which would
  // call the API on port 8000).
  const nextBin = join(webDir, "node_modules", "next", "dist", "bin", "next");
  const marker = join(webDir, ".next", "e2e-build.json");
  const buildKey = JSON.stringify({ api: apiUrl, clerk: clerk.frontendApi });
  const reusable = existsSync(marker) && readFileSync(marker, "utf8") === buildKey;
  if (skipBuild && !reusable) log("no e2e build to reuse; building");
  if (!skipBuild || !reusable) {
    run("web-build", process.execPath, [nextBin, "build"], { cwd: webDir, env: webEnv });
    writeFileSync(marker, buildKey);
  }

  // 3. API, worker and web. The API and worker run from apps/api/scripts/e2e, where no .env
  // file is loaded, so only the values above apply.
  const uvicornArgs = ["-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", String(API_PORT), "--no-access-log"];
  if (isWindows) uvicornArgs.push("--loop", "asyncio:SelectorEventLoop"); // the job queue's driver needs it
  // One worker per lane, as in production (scripts/worker.sh, TR-JOB-06), so a sandbox account's
  // backfill never holds up a webhook or a suggestion. Lower concurrency than production: the
  // suite doesn't need more, and it keeps connections to a shared Postgres down.
  const lanes = [
    ["worker-interactive", "interactive", "10"],
    ["worker-bulk", "bulk", "4"],
  ];
  // A process that stops while starting (say, Postgres was slow to accept connections) gets
  // one more try before the run fails.
  await startReady("api", py, uvicornArgs, { cwd: e2ePy, env: apiEnv }, (child) =>
    waitFor("The API", `http://127.0.0.1:${API_PORT}/readyz`, child, 90_000),
  );
  for (const [name, lane, concurrency] of lanes) {
    const workerArgs = [join(e2ePy, "worker.py"), `--queues=${lane}`, `--concurrency=${concurrency}`];
    await startReady(name, py, workerArgs, { cwd: e2ePy, env: apiEnv }, (child) =>
      waitForLog(`The ${name}`, child, /Launching a worker|Starting worker/i, 60_000),
    );
  }
  await startReady("web", process.execPath, [nextBin, "start", "--port", String(WEB_PORT)], { cwd: webDir, env: webEnv }, (child) =>
    waitFor("The web app", `http://127.0.0.1:${WEB_PORT}/`, child, 90_000),
  );
  log(`stack ready in ${Math.round((Date.now() - started) / 1000)} s`);

  if (serve) {
    writeFileSync(stackFile, JSON.stringify(stack, null, 2));
    log(`serving; run \`pnpm exec playwright test\` in apps/web. Ctrl-C stops the stack.`);
    await new Promise((resolve) => {
      for (const child of children) child.on("exit", resolve);
    });
    fail("a stack process stopped");
  }

  // 4. Playwright.
  const testStarted = Date.now();
  const playwright = spawn(
    process.execPath,
    [join(webDir, "node_modules", "@playwright", "test", "cli.js"), "test", ...playwrightArgs],
    {
      cwd: webDir,
      stdio: "inherit",
      env: { ...process.env, ...stack, CLERK_PUBLISHABLE_KEY: clerk.publishable, CLERK_SECRET_KEY: clerk.secret },
    },
  );
  const code = await new Promise((resolve) => playwright.on("exit", (c) => resolve(c ?? 1)));
  log(`playwright finished in ${Math.round((Date.now() - testStarted) / 1000)} s (exit ${code})`);
  process.exitCode = code;
}

async function teardown() {
  stopping = true;
  rmSync(stackFile, { force: true });
  for (const child of children) stop(child);
  await new Promise((r) => setTimeout(r, 1500));
  for (const child of children) stop(child, "SIGKILL");
  if (keepDb) return;
  try {
    const env = { ...process.env, DATABASE_URL_DIRECT: `${PG}/${DB_NAME}`, REDIS_URL };
    spawnSync(python(), [join(e2ePy, "db.py"), "drop"], { cwd: e2ePy, env, stdio: "ignore" });
  } catch {
    // best effort: the next run resets it anyway
  }
}

let tornDown = false;
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (tornDown) return;
    tornDown = true;
    log(`${signal}: stopping the stack`);
    void teardown().then(() => process.exit(130));
  });
}

try {
  await main();
} catch (error) {
  process.exitCode = process.exitCode || 1;
  console.error(error instanceof StackError ? `[e2e] ${error.message}` : error);
} finally {
  if (!tornDown) {
    tornDown = true;
    await teardown();
  }
}
