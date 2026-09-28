import { SignUp } from "@clerk/nextjs";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Create your account" };

/** FR-ACC-01 and F-01: sign-up lands on /app, which provisions the first workspace. */
export default function SignUpPage() {
  return <SignUp signInUrl="/sign-in" fallbackRedirectUrl="/app" />;
}
