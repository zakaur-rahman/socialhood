import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/AuthShell";
import { ThemedSignIn } from "@/components/auth/ThemedClerk";

export const metadata: Metadata = { title: "Sign in" };

/** FR-ACC-01: Clerk's sign-in, dark themed. After sign-in, /app picks the workspace (F-02). */
export default function SignInPage() {
  return (
    <AuthShell mode="sign-in">
      <ThemedSignIn />
    </AuthShell>
  );
}
