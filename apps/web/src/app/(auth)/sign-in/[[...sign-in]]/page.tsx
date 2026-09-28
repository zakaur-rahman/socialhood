import { SignIn } from "@clerk/nextjs";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sign in" };

/** FR-ACC-01: Clerk's sign-in, dark themed. After sign-in, /app picks the workspace (F-02). */
export default function SignInPage() {
  return <SignIn signUpUrl="/sign-up" fallbackRedirectUrl="/app" />;
}
