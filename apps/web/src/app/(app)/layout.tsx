import type { Metadata } from "next";

import { PrelaunchNotice } from "@/components/shell/PrelaunchNotice";
import { ShellSkeleton } from "@/components/shell/ShellFrame";
import { ApiProvider } from "@/lib/api/provider";
import { NO_INDEX } from "@/lib/marketing/seo";

// The signed-in app is never a search result (C-142); robots.txt keeps crawlers out too.
export const metadata: Metadata = { robots: NO_INDEX };

/**
 * A production build made without an API (the website-only deploy, C-145) has no app to run:
 * signed-in visitors get the pre-launch notice instead of screens whose every request fails.
 * Development and test builds always run the app.
 */
const PRELAUNCH = process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_BASE_URL;

/**
 * Everything signed in shares one API client and query cache (TR-FE-02). While it loads, the shell
 * frame is already there (the workspace layout shows the same skeleton next), so a hard load
 * doesn't paint a bare page first.
 */
export default function SignedInLayout({ children }: LayoutProps<"/">) {
  if (PRELAUNCH) return <PrelaunchNotice />;
  return <ApiProvider fallback={<ShellSkeleton />}>{children}</ApiProvider>;
}
