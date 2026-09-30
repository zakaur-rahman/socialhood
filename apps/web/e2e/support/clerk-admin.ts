/**
 * The few Clerk Backend API calls the suite makes, with CLERK_SECRET_KEY (a development
 * instance). Plain fetch, so the suite needs no Clerk SDK beyond @clerk/testing.
 */
const CLERK_API = "https://api.clerk.com/v1";

type ClerkUser = { id: string; email_addresses: { email_address: string }[] };

function secret(): string {
  const key = process.env.CLERK_SECRET_KEY;
  if (!key?.startsWith("sk_test_")) {
    throw new Error("CLERK_SECRET_KEY must be set to a development instance's key (sk_test_…).");
  }
  return key;
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    const response = await fetch(`${CLERK_API}${path}`, {
      method,
      headers: { Authorization: `Bearer ${secret()}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 429 && attempt < 4) {
      await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt));
      continue;
    }
    if (!response.ok) {
      // Clerk's error bodies name the problem, never the key.
      throw new Error(`Clerk ${method} ${path.split("?")[0]}: HTTP ${response.status} ${await response.text()}`);
    }
    return (await response.json()) as T;
  }
}

export async function findUsers(query: { emailAddress?: string; query?: string }): Promise<ClerkUser[]> {
  const params = new URLSearchParams({ limit: "100" });
  if (query.emailAddress) params.append("email_address", query.emailAddress);
  if (query.query) params.set("query", query.query);
  return call<ClerkUser[]>("GET", `/users?${params}`);
}

/** The user with this email, created if missing (idempotent). */
export async function ensureUser(user: { email: string; firstName: string; lastName: string }): Promise<string> {
  const [existing] = await findUsers({ emailAddress: user.email });
  if (existing) return existing.id;
  const created = await call<ClerkUser>("POST", "/users", {
    email_address: [user.email],
    first_name: user.firstName,
    last_name: user.lastName,
    skip_password_requirement: true,
  });
  return created.id;
}

export async function deleteUser(userId: string): Promise<void> {
  await call("DELETE", `/users/${userId}`);
}

/** Users whose email starts with ``prefix`` (sign-up leftovers). */
export async function usersWithEmailPrefix(prefix: string): Promise<ClerkUser[]> {
  const found = await findUsers({ query: prefix });
  return found.filter((u) => u.email_addresses.some((e) => e.email_address.startsWith(prefix)));
}
