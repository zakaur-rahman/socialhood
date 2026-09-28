// Regenerates the API contract (TR-API-08): apps/api/openapi.json from FastAPI, then
// packages/api-client/schema.d.ts from that file. CI runs this and fails if either changes.
// Set UV to the uv executable if it is not on PATH.
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = join(root, "apps", "api");
const clientDir = join(root, "packages", "api-client");
const uv = process.env.UV ?? "uv";

const document = execFileSync(uv, ["run", "--quiet", "python", "-m", "socialhood.openapi"], {
  cwd: apiDir,
  encoding: "utf8",
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});
writeFileSync(join(apiDir, "openapi.json"), document.replace(/\r\n/g, "\n"));

// Run the generator's CLI with this Node binary (no shell, so arguments are never re-parsed).
const require = createRequire(join(clientDir, "package.json"));
const cli = join(dirname(require.resolve("openapi-typescript/package.json")), "bin", "cli.js");
execFileSync(
  process.execPath,
  [cli, join(apiDir, "openapi.json"), "-o", join(clientDir, "schema.d.ts")],
  { cwd: clientDir, stdio: "inherit" },
);
console.log("Wrote apps/api/openapi.json and packages/api-client/schema.d.ts");
