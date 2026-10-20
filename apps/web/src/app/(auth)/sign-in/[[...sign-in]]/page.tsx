import { SignIn } from "@clerk/nextjs";
import type { Metadata } from "next";

import { AuthShell, authAppearance } from "@/components/auth/AuthShell";

export const metadata: Metadata = { title: "Sign in" };

/** FR-ACC-01: Clerk's sign-in, dark themed. After sign-in, /app picks the workspace (F-02). */
export default function SignInPage() {
  return (
    <AuthShell mode="sign-in">
      <SignIn signUpUrl="/sign-up" fallbackRedirectUrl="/app" appearance={authAppearance} />
    </AuthShell>
  );
}
