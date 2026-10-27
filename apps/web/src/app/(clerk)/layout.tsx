import type { Metadata } from "next";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { appOrigin } from "@/lib/marketing/site";
import { manifestLink } from "@/lib/pwa/manifest";

// With the app on its own host the app installs from here, not from the public site (C-148).
export const metadata: Metadata = manifestLink().app;

/**
 * The signed-in app and Clerk's sign-in and sign-up pages: the pages that need Clerk's client. With
 * the app on its own host they get Clerk's provider here, once for both groups, so moving from
 * sign-in into the app keeps it mounted; the public pages then load none of Clerk (C-148). With one
 * origin the root layout already wraps every page in it.
 */
export default function ClerkLayout({ children }: LayoutProps<"/">) {
  if (!appOrigin()) return children;
  return <AuthProvider>{children}</AuthProvider>;
}
