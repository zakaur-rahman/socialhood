import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/AuthShell";
import { ThemedSignUp } from "@/components/auth/ThemedClerk";

export const metadata: Metadata = { title: "Create your account" };

/** FR-ACC-01 and F-01: sign-up lands on /app, which provisions the first workspace. */
export default function SignUpPage() {
  return (
    <AuthShell mode="sign-up">
      <ThemedSignUp />
    </AuthShell>
  );
}
