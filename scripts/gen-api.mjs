// Regenerates the API contract (TR-API-08): apps/api/openapi.json from FastAPI, then
// packages/api-client/schema.d.ts from that file. CI runs this and fails if either changes.
// Set UV to the uv executable if it is not on PATH.
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = join(root, "apps", "api");
const clientDir = join(root, "packages", "api-client");
const uv = process.env.UV ?? "uv";

// Importing the app reads settings, but the export never connects to anything: placeholders let
// it run where there is no apps/api/.env (CI, fresh checkouts, worktrees). Real values win.
const placeholders = {
  DATABASE_URL: "postgresql+asyncpg://openapi:openapi@localhost:5432/openapi",
  DATABASE_URL_DIRECT: "postgresql://openapi:openapi@localhost:5432/openapi",
  REDIS_URL: "redis://localhost:6379/0",
};

// The Python script writes the file itself, so log lines on stdout never reach the contract.
execFileSync(uv, ["run", "--quiet", "python", "-m", "socialhood.openapi", "openapi.json"], {
  cwd: apiDir,
  stdio: ["ignore", "ignore", "inherit"],
  env: { ...placeholders, ...process.env, PYTHONIOENCODING: "utf-8" },
});

// Run the generator's CLI with this Node binary (no shell, so arguments are never re-parsed).
const require = createRequire(join(clientDir, "package.json"));
const cli = join(dirname(require.resolve("openapi-typescript/package.json")), "bin", "cli.js");
execFileSync(
  process.execPath,
  [cli, join(apiDir, "openapi.json"), "-o", join(clientDir, "schema.d.ts")],
  { cwd: clientDir, stdio: "inherit" },
);
console.log("Wrote apps/api/openapi.json and packages/api-client/schema.d.ts");
