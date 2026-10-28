"use client";

import type { ReactNode } from "react";

import { useSignedIn } from "@/components/auth/signed-in";

/** Shows `signedIn` or `signedOut`, both rendered on the server, by what the browser knows (C-152). */
export function SignedInSwitch({ signedIn, signedOut }: { signedIn: ReactNode; signedOut: ReactNode }) {
  return useSignedIn() ? signedIn : signedOut;
}
