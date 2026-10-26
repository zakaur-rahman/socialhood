import type { Metadata } from "next";

import { ShellSkeleton } from "@/components/shell/ShellFrame";
import { ApiProvider } from "@/lib/api/provider";
import { NO_INDEX } from "@/lib/marketing/seo";

// The signed-in app is never a search result (C-142); robots.txt keeps crawlers out too.
export const metadata: Metadata = { robots: NO_INDEX };

/**
 * Everything signed in shares one API client and query cache (TR-FE-02). While it loads, the shell
 * frame is already there (the workspace layout shows the same skeleton next), so a hard load
 * doesn't paint a bare page first.
 */
export default function SignedInLayout({ children }: LayoutProps<"/">) {
  return <ApiProvider fallback={<ShellSkeleton />}>{children}</ApiProvider>;
}
