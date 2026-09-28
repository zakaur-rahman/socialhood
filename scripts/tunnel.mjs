// A public HTTPS address for the local API (F-03, TR-WH-01). Instagram only redirects to, and
// delivers webhooks to, public HTTPS URLs. This starts `ngrok http 8000`, points
// IG_REDIRECT_URI and API_BASE_URL in apps/api/.env at the tunnel, and prints the URLs to
// register in the Meta app. The web app keeps calling the API on localhost.
//
// Set NGROK_DOMAIN in apps/api/.env (or the environment) to your ngrok dev domain so the URL
// never changes between runs; otherwise every change means re-registering it with Meta.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const envPath = join(root, "apps", "api", ".env");
const port = process.env.API_PORT ?? "8000";
const ngrok = process.env.NGROK ?? "ngrok";

function readEnv(text) {
  const values = {};
  for (const line of text.split(/\r?\n/)) {
    const match = /^([A-Z0-9_]+)=(.*)$/.exec(line);
    if (match) values[match[1]] = match[2].trim();
  }
  return values;
}

function setEnv(text, key, value) {
  const line = `${key}=${value}`;
  const pattern = new RegExp(`^${key}=.*$`, "m");
  return pattern.test(text) ? text.replace(pattern, line) : `${text.replace(/\n?$/, "\n")}${line}\n`;
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

// 1. ngrok installed? (Whether it is signed in is reported by ngrok itself when it starts: the
// Microsoft Store build keeps its config in a private folder other programs cannot read.)
if (spawnSync(ngrok, ["version"], { encoding: "utf8" }).error) {
  fail("ngrok is not installed. Install it (winget install ngrok.ngrok), then run this again.");
}
if (!existsSync(envPath)) fail("apps/api/.env is missing; copy apps/api/.env.example first.");
const SIGN_IN_HELP = [
  "ngrok is not signed in. Copy your authtoken from",
  "  https://dashboard.ngrok.com/get-started/your-authtoken",
  "and run, in your own terminal:",
  "  ngrok config add-authtoken <your-token>",
  "Then run `pnpm tunnel` again.",
].join("\n");

// 2. Start the tunnel and wait for its public URL.
const env = readEnv(readFileSync(envPath, "utf8"));
const domain = (process.env.NGROK_DOMAIN ?? env.NGROK_DOMAIN ?? "").replace(/^https?:\/\//, "").replace(/\/$/, "");
const args = ["http", port, "--log", "stdout", "--log-format", "json"];
if (domain) args.push("--url", `https://${domain}`);

const child = spawn(ngrok, args, { stdio: ["ignore", "pipe", "pipe"] });
let explainedSignIn = false;
createInterface({ input: child.stderr }).on("line", (line) => {
  if (/authentication failed|ERR_NGROK_(4018|401)\b/.test(line)) {
    if (!explainedSignIn) console.error(SIGN_IN_HELP);
    explainedSignIn = true;
  } else if (line.trim() && !explainedSignIn) {
    console.error(line);
  }
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill());
child.on("exit", (code) => process.exit(code ?? 0));

let announced = false;
function announce(url) {
  if (announced) return;
  announced = true;
  onTunnel(url.replace(/\/$/, ""));
}

createInterface({ input: child.stdout }).on("line", (line) => {
  let entry;
  try {
    entry = JSON.parse(line);
  } catch {
    return;
  }
  const problem = String(entry.err ?? entry.msg);
  // Sign-in failures are explained once from stderr; other errors are passed on.
  if (["eror", "crit"].includes(entry.lvl) && !/authentication failed/.test(problem)) {
    console.error(`ngrok: ${problem}`);
  }
  if (entry.msg === "started tunnel" && String(entry.url).startsWith("https://")) announce(entry.url);
});

// Fallback if the log line changes: ask the agent's local API for its public URL.
const poll = setInterval(async () => {
  if (announced) return clearInterval(poll);
  try {
    const response = await fetch("http://127.0.0.1:4040/api/tunnels");
    const { tunnels = [] } = await response.json();
    const https = tunnels.find((t) => String(t.public_url).startsWith("https://"));
    if (https) announce(https.public_url);
  } catch {
    // the agent is still starting
  }
}, 1500);
child.on("exit", () => clearInterval(poll));

// 3. Point the API at the tunnel and say what to register with Meta.
function onTunnel(url) {
  const redirect = `${url}/v1/oauth/instagram/callback`;
  const before = readFileSync(envPath, "utf8");
  const previous = readEnv(before).IG_REDIRECT_URI;
  let after = setEnv(before, "IG_REDIRECT_URI", redirect);
  after = setEnv(after, "API_BASE_URL", url);
  if (after !== before) writeFileSync(envPath, after);

  const lines = [
    "",
    `Tunnel: ${url} -> http://localhost:${port}   (inspect traffic at http://127.0.0.1:4040)`,
    "",
    "Register these in the Meta app (Instagram > API setup with Instagram login):",
    `  OAuth redirect URI ............ ${redirect}`,
    `  Webhook callback URL .......... ${url}/webhooks/instagram`,
    "  Webhook verify token .......... the IG_WEBHOOK_VERIFY_TOKEN value in apps/api/.env",
    `  Deauthorize callback URL ...... ${url}/webhooks/meta/deauthorize`,
    `  Data deletion request URL ..... ${url}/webhooks/meta/data-deletion`,
    "",
  ];
  if (previous !== redirect) {
    lines.push(
      "Updated IG_REDIRECT_URI and API_BASE_URL in apps/api/.env. Restart the API so it uses them.",
    );
    if (previous?.startsWith("https://")) {
      lines.push("The address changed since last time: update the URLs above in the Meta app too.");
    }
  }
  if (!domain) {
    lines.push(
      "Tip: set NGROK_DOMAIN in apps/api/.env to your dev domain (https://dashboard.ngrok.com/domains)",
      "so this address stays the same every run.",
    );
  }
  lines.push("", "Leave this running; Ctrl+C stops the tunnel.");
  console.log(lines.join("\n"));
}
